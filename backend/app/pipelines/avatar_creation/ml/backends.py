"""ML backend abstraction for the avatar-creation pipeline.

Two implementations satisfy the same interface:

- RealBackend: lazily imports torch / torchaudio / insightface / f5_tts and runs
  the production code described in AVATAR_CREATION_PIPELINE.md (§4–§7). Requires
  a GPU and the model weights under ml_models/weights/.
- StubBackend: uses only ffmpeg + the standard library to produce VALID
  placeholder artifacts with the correct shapes/paths, so the full pipeline,
  state machine, and profile.json contract run and can be tested without a GPU.

`loaders.get_backend()` picks the backend from settings.PIPELINE_BACKEND
("auto" → real if importable, else stub).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Protocol

from app.core.logging import get_logger
from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.ml.ffmpeg import ffprobe_metadata, run_ffmpeg

logger = get_logger("pipeline.backend")

F5_VERSION = "f5-tts-base-v1"
LIVEPORTRAIT_VERSION = "liveportrait-v1"
INSIGHTFACE_MODEL = "buffalo_l"
MUSETALK_TARGET = "musetalk-v1"


def _ffmpeg_select_face(
    frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
) -> dict:
    """Pick a frame with ffmpeg only (no insightface) and write face/thumb/half-body.

    Used by the stub, and by RealBackend when settings.USE_INSIGHTFACE is False
    (lets the EchoMimic path skip the heavy envLP env on small-disk hosts). The
    half-body reference is the full chosen frame (head+torso+arms) for EchoMimic v2;
    likeness then depends on a clean, frontal upload rather than detector framing.
    """
    out_face.parent.mkdir(parents=True, exist_ok=True)
    frames = sorted(frame_dir.glob("*.jpg"))
    if not frames:
        raise PipelineError("NO_FACE_DETECTED", "no frames sampled from video")
    chosen = frames[len(frames) // 2]
    run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=512:512", str(out_face)])
    run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=256:256", str(out_thumb)])
    run_ffmpeg(["-y", "-i", str(chosen), str(out_halfbody)])  # full frame, native size
    return {
        "bbox": [0, 0, 512, 512],
        "crop_size": [512, 512],
        "quality_score": 0.5,
        "pose_samples": [],
    }


def _ffmpeg_prep_driving(source_video: Path, out_driving: Path, *, seconds: float = 6.0) -> dict:
    """Cut a centered clip with ffmpeg only (no insightface windowing)."""
    out_driving.parent.mkdir(parents=True, exist_ok=True)
    meta = ffprobe_metadata(source_video)
    dur = float(meta.get("duration_seconds") or seconds)
    start = max(0.0, dur / 2 - seconds / 2)
    run_ffmpeg(
        [
            "-y",
            "-ss",
            f"{start:.2f}",
            "-i",
            str(source_video),
            "-t",
            f"{seconds:.2f}",
            "-r",
            "25",
            "-an",
            str(out_driving),
        ]
    )
    return {"path": str(out_driving), "model": LIVEPORTRAIT_VERSION}


class AvatarBackend(Protocol):
    name: str

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict: ...

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict: ...

    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict: ...

    def prep_driving(self, source_video: Path, out_driving: Path) -> dict: ...


# --------------------------------------------------------------------------- #
# Stub backend — ffmpeg + stdlib only
# --------------------------------------------------------------------------- #
class StubBackend:
    """Deterministic, GPU-free backend producing valid placeholder artifacts."""

    name = "stub"

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict:
        # Take up to the first 15s as the reference clip.
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(source_audio),
                "-t",
                "15",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(out_reference),
            ]
        )
        transcript = " ".join((script_text or "reference audio sample").split()[:40])
        return {
            "reference_path": str(out_reference),
            "transcript": transcript,
            "qc": {"snr_db": None, "clip_ratio": None, "stub": True},
            "duration_s": 15.0,
        }

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict:
        # F5-TTS is reference-based; the artifact is a small profile, not weights.
        artifact = {
            "kind": "f5tts_voice_profile",
            "backend": "stub",
            "model_version": F5_VERSION,
            "sample_rate": sample_rate,
            "reference_path": str(reference),
            "reference_text": transcript,
        }
        with out_model.open("wb") as fh:
            pickle.dump(artifact, fh)
        return {"model_path": str(out_model), "model_version": F5_VERSION}

    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict:
        return _ffmpeg_select_face(frame_dir, out_face, out_thumb, out_halfbody)

    def prep_driving(self, source_video: Path, out_driving: Path) -> dict:
        return _ffmpeg_prep_driving(source_video, out_driving, seconds=6.0)


# --------------------------------------------------------------------------- #
# Real backend — lazy heavy imports (production path)
# --------------------------------------------------------------------------- #
class RealBackend:
    """Production backend via subprocess into the isolated micromamba envs.

    Importing this module never pulls in torch/insightface; every ML-heavy step
    shells out through ml_models/runners/mrun.sh into envF5 (F5-TTS/Whisper) or
    envLP (insightface). Each avatar's motion profile (driving.mp4) is cut from
    its OWN uploaded video by prep_driving and later replayed by LivePortrait at
    generation time (see VIDEO_GENERATION_PIPELINE).
    """

    name = "real"

    @staticmethod
    def is_available() -> bool:
        from app.core.config import settings

        return Path(settings.AI_ROOT, "mamba", "envs", settings.ENV_F5).exists()

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict:  # pragma: no cover - requires ML stack
        # ffmpeg-only: take the first ~10s as a clean mono 24 kHz reference clip.
        # (F5-TTS wants <=12s clean speech; the transcript is captured separately
        # by build_voice_model via Whisper.)
        out_reference.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(source_audio),
                "-t",
                "10",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(out_reference),
            ]
        )
        return {
            "reference_path": str(out_reference),
            "transcript": "",
            "qc": {},
            "duration_s": 10.0,
        }

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict:  # pragma: no cover - requires ML stack
        # F5-TTS is in-context (no .pt to train). The reusable artifact is the
        # reference wav + its transcript; capture the transcript once with Whisper
        # so each later generation passes an explicit --ref-text.
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        txt = reference.with_suffix(".txt")
        run_in_env(
            settings.ENV_F5,
            [
                "python",
                f"{Path(settings.RUNNERS_DIR).resolve()}/transcribe.py",
                "--audio",
                str(reference),
                "--out",
                str(txt),
            ],
        )
        ref_text = txt.read_text().strip() if txt.exists() else ""
        return {
            "model_path": str(txt),
            "model_version": "f5-incontext",
            "transcript_path": str(txt),
            "reference_text": ref_text,
        }

    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        from app.core.config import settings

        # Small-disk hosts (EchoMimic-only) skip envLP: pick the frame with ffmpeg.
        if not settings.USE_INSIGHTFACE:
            return _ffmpeg_select_face(frame_dir, out_face, out_thumb, out_halfbody)

        from app.pipelines._subproc import run_in_env

        out_face.parent.mkdir(parents=True, exist_ok=True)
        stdout = run_in_env(
            settings.ENV_LP,
            [
                "python",
                f"{Path(settings.RUNNERS_DIR).resolve()}/select_face.py",
                "--frames",
                str(frame_dir),
                "--out-face",
                str(out_face),
                "--out-thumb",
                str(out_thumb),
                "--out-halfbody",
                str(out_halfbody),
            ],
        )
        result = _parse_last_json(stdout)
        if result is None:
            raise PipelineError("NO_FACE_DETECTED", "select_face.py produced no JSON result")
        if result.get("error"):
            raise PipelineError("NO_FACE_DETECTED", "no face found in sampled frames")
        return result

    def prep_driving(
        self, source_video: Path, out_driving: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        # The avatar's motion profile = a frontal, stable window cut from its OWN
        # uploaded video. insightface (envLP) picks the window; ffmpeg cuts it at
        # 25 fps. This clip is later palindrome-looped to the speech length and
        # used as the LivePortrait driving input at generation time.
        from app.core.config import settings

        # Small-disk hosts (EchoMimic-only) skip envLP: centered ffmpeg window. The
        # driving clip is unused by the echomimic engine, but keep the artifact.
        if not settings.USE_INSIGHTFACE:
            return _ffmpeg_prep_driving(source_video, out_driving, seconds=settings.DRIVING_SECONDS)

        from app.pipelines._subproc import run_in_env

        out_driving.parent.mkdir(parents=True, exist_ok=True)
        stdout = run_in_env(
            settings.ENV_LP,
            [
                "python",
                f"{Path(settings.RUNNERS_DIR).resolve()}/extract_driving.py",
                "--video",
                str(source_video),
                "--window-seconds",
                str(settings.DRIVING_SECONDS),
            ],
        )
        window = _parse_last_json(stdout) or {}
        if window.get("error") or "start" not in window:
            # Fallback: centered window (e.g. detector cold or no clean frontal span).
            meta = ffprobe_metadata(source_video)
            dur = float(meta.get("duration_seconds") or settings.DRIVING_SECONDS)
            start = max(0.0, dur / 2 - settings.DRIVING_SECONDS / 2)
        else:
            start = float(window["start"])
        run_ffmpeg(
            [
                "-y",
                "-ss",
                f"{start:.2f}",
                "-i",
                str(source_video),
                "-t",
                f"{settings.DRIVING_SECONDS:.2f}",
                "-r",
                "25",
                "-an",
                str(out_driving),
            ]
        )
        return {"path": str(out_driving), "model": LIVEPORTRAIT_VERSION, "window_start_s": start}


def _parse_last_json(stdout: str) -> dict | None:
    """Return the last JSON object printed on stdout (envs print loader noise too)."""
    import json

    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None
