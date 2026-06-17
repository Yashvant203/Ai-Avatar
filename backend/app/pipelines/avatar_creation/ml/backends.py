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
from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg

logger = get_logger("pipeline.backend")

F5_VERSION = "f5-tts-base-v1"
LIVEPORTRAIT_VERSION = "liveportrait-v1"
INSIGHTFACE_MODEL = "buffalo_l"
MUSETALK_TARGET = "musetalk-v1"


class AvatarBackend(Protocol):
    name: str

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict: ...

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict: ...

    def select_best_face(self, frame_dir: Path, out_face: Path, out_thumb: Path) -> dict: ...

    def prep_appearance(self, face: Path, out_template: Path) -> dict: ...


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

    def select_best_face(self, frame_dir: Path, out_face: Path, out_thumb: Path) -> dict:
        frames = sorted(frame_dir.glob("*.jpg"))
        if not frames:
            raise PipelineError("NO_FACE_DETECTED", "no frames sampled from video")
        # Use the middle frame; scale to the documented sizes via ffmpeg.
        chosen = frames[len(frames) // 2]
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=512:512", str(out_face)])
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=256:256", str(out_thumb)])
        return {
            "bbox": [0, 0, 512, 512],
            "crop_size": [512, 512],
            "quality_score": 0.5,
            "pose_samples": [],
        }

    def prep_appearance(self, face: Path, out_template: Path) -> dict:
        template = {
            "kind": "liveportrait_appearance",
            "backend": "stub",
            "model_version": LIVEPORTRAIT_VERSION,
            "source_face": str(face),
        }
        with out_template.open("wb") as fh:
            pickle.dump(template, fh)
        return {"path": str(out_template), "model": LIVEPORTRAIT_VERSION}


# --------------------------------------------------------------------------- #
# Real backend — lazy heavy imports (production path)
# --------------------------------------------------------------------------- #
class RealBackend:
    """Production backend via subprocess into the isolated micromamba envs.

    Importing this module never pulls in torch/insightface; every ML-heavy step
    shells out through ml_models/runners/mrun.sh into envF5 (F5-TTS/Whisper) or
    envLP (insightface). Appearance prep is a no-op — animation is recomputed per
    generation from the shared idle-motion clip (see VIDEO_GENERATION_PIPELINE).
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
            ["-y", "-i", str(source_audio), "-t", "10", "-ac", "1", "-ar", "24000", str(out_reference)]
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
            ["python", f"{settings.RUNNERS_DIR}/transcribe.py", "--audio", str(reference), "--out", str(txt)],
        )
        ref_text = txt.read_text().strip() if txt.exists() else ""
        return {
            "model_path": str(txt),
            "model_version": "f5-incontext",
            "transcript_path": str(txt),
            "reference_text": ref_text,
        }

    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_face.parent.mkdir(parents=True, exist_ok=True)
        stdout = run_in_env(
            settings.ENV_LP,
            [
                "python",
                f"{settings.RUNNERS_DIR}/select_face.py",
                "--frames",
                str(frame_dir),
                "--out-face",
                str(out_face),
                "--out-thumb",
                str(out_thumb),
            ],
        )
        result = _parse_last_json(stdout)
        if result is None:
            raise PipelineError("NO_FACE_DETECTED", "select_face.py produced no JSON result")
        if result.get("error"):
            raise PipelineError("NO_FACE_DETECTED", "no face found in sampled frames")
        return result

    def prep_appearance(
        self, face: Path, out_template: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        # No per-avatar template: the shared idle motion drives animation at
        # generation time, so this stage is validation/placeholder only.
        out_template.parent.mkdir(parents=True, exist_ok=True)
        out_template.write_bytes(b"")
        return {"path": str(out_template), "model": LIVEPORTRAIT_VERSION}


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
