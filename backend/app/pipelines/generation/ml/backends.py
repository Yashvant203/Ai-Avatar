"""Generation ML backend abstraction (mirrors the avatar-creation pattern).

- RealBackend: lazily imports f5_tts / LivePortrait / MuseTalk and runs the
  production stages (VIDEO_GENERATION_PIPELINE.md §3–§5). Requires a GPU + weights.
- StubBackend: ffmpeg-only stages that produce a REAL, playable output.mp4 (a
  still-face video timed to synthesized audio), so generate → download works
  end-to-end without a GPU.

ffmpeg muxing is shared (steps.mux), not backend-specific.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from app.core.logging import get_logger
from app.pipelines.avatar_creation.ml.ffmpeg import ffprobe_metadata, run_ffmpeg

logger = get_logger("generation.backend")

F5_VERSION = "f5-tts-base-v1"
LIVEPORTRAIT_VERSION = "liveportrait-v1"
MUSETALK_VERSION = "musetalk-v1"


class GenerationBackend(Protocol):
    name: str

    def synthesize_speech(
        self, out_speech: Path, *, script_text: str, voice_ref: Path | None, duration_s: float
    ) -> float: ...

    def animate(
        self,
        out_animated: Path,
        *,
        face: Path | None,
        driving: Path | None,
        duration_s: float,
        fps: int,
    ) -> None: ...

    def lipsync(self, animated: Path, speech: Path, out_lipsync: Path) -> None: ...


class StubBackend:
    """GPU-free stages built on ffmpeg. Produces real, playable artifacts."""

    name = "stub"

    def synthesize_speech(
        self, out_speech: Path, *, script_text: str, voice_ref: Path | None, duration_s: float
    ) -> float:
        # A gentle 24 kHz mono tone of the estimated duration stands in for TTS.
        out_speech.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=180:duration={duration_s:.3f}:sample_rate=24000",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(out_speech),
            ]
        )
        return duration_s

    def animate(
        self,
        out_animated: Path,
        *,
        face: Path | None,
        driving: Path | None = None,
        duration_s: float,
        fps: int,
    ) -> None:
        # The stub has no reenactment model; it animates the still face. `driving`
        # is accepted for interface parity but unused.
        out_animated.parent.mkdir(parents=True, exist_ok=True)
        if face is not None and Path(face).exists():
            run_ffmpeg(
                [
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(face),
                    "-t",
                    f"{duration_s:.3f}",
                    "-r",
                    str(fps),
                    "-vf",
                    "scale=512:512",
                    "-pix_fmt",
                    "yuv420p",
                    str(out_animated),
                ]
            )
        else:
            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc=duration={duration_s:.3f}:size=512x512:rate={fps}",
                    "-pix_fmt",
                    "yuv420p",
                    str(out_animated),
                ]
            )

    def lipsync(self, animated: Path, speech: Path, out_lipsync: Path) -> None:
        # The stub has no mouth model; the lip-synced clip is the animated clip.
        shutil.copyfile(animated, out_lipsync)


class RealBackend:
    """Production stages via subprocess into the isolated micromamba envs.

    Each stage shells out through ml_models/runners/mrun.sh into envF5 / envLP /
    envMT (the Phase-0 proven runners). File-based hand-off between stages keeps
    the heavy ML stacks out of this process entirely.
    """

    name = "real"

    @staticmethod
    def is_available() -> bool:
        from app.core.config import settings

        return Path(settings.AI_ROOT, "mamba", "envs", settings.ENV_F5).exists()

    def synthesize_speech(
        self, out_speech: Path, *, script_text: str, voice_ref: Path | None, duration_s: float
    ) -> float:  # pragma: no cover - requires ML stack
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_speech.parent.mkdir(parents=True, exist_ok=True)
        runners = settings.RUNNERS_DIR
        transcript = voice_ref.with_suffix(".txt") if voice_ref else None
        ref_text = transcript.read_text().strip() if transcript and transcript.exists() else ""
        run_in_env(
            settings.ENV_F5,
            [
                "python",
                f"{runners}/run_f5tts.py",
                "--ref",
                str(voice_ref),
                "--ref-text",
                ref_text,
                "--gen-text",
                script_text,
                "--out",
                str(out_speech),
            ],
        )
        # Measure the real synthesized duration with ffprobe (no torch in this env).
        meta = ffprobe_metadata(out_speech)
        return float(meta.get("duration_seconds") or duration_s)

    def animate(
        self,
        out_animated: Path,
        *,
        face: Path | None,
        driving: Path | None = None,
        duration_s: float,
        fps: int,
    ) -> None:  # pragma: no cover - requires ML stack
        import glob

        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_animated.parent.mkdir(parents=True, exist_ok=True)
        # Drive with the avatar's OWN motion clip (cut from its upload); fall back
        # to the optional global idle clip only if the avatar has none.
        src_drive = (
            str(driving) if driving and Path(driving).exists() else settings.IDLE_MOTION_PATH
        )
        # Build a seamless palindrome (forward+reverse) so the loop has no jump-cut,
        # then loop it to >= speech duration at the target fps.
        boomerang = out_animated.parent / "driving_boomerang.mp4"
        run_ffmpeg(
            [
                "-y",
                "-i",
                src_drive,
                "-filter_complex",
                "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[v]",
                "-map",
                "[v]",
                "-an",
                str(boomerang),
            ]
        )
        looped = out_animated.parent / "driving_loop.mp4"
        run_ffmpeg(
            [
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(boomerang),
                "-t",
                f"{duration_s:.2f}",
                "-r",
                str(fps),
                str(looped),
            ]
        )
        out_dir = out_animated.parent / "lp_out"
        run_in_env(
            settings.ENV_LP,
            [
                "bash",
                f"{settings.RUNNERS_DIR}/run_liveportrait.sh",
                str(face),
                str(looped),
                str(out_dir),
                settings.AI_ROOT,
            ],
        )
        # Pick LivePortrait's clean output (NOT the *_concat comparison clip).
        candidates = [f for f in sorted(glob.glob(f"{out_dir}/*.mp4")) if "concat" not in f]
        if not candidates:
            raise RuntimeError(f"LivePortrait produced no clean output in {out_dir}")
        clean = candidates[-1]
        # Normalize to the target fps so MuseTalk gets exactly 25 fps.
        run_ffmpeg(["-y", "-i", clean, "-r", str(fps), str(out_animated)])

    def lipsync(
        self, animated: Path, speech: Path, out_lipsync: Path
    ) -> None:  # pragma: no cover - requires ML stack
        import glob
        import shutil

        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_lipsync.parent.mkdir(parents=True, exist_ok=True)
        # MuseTalk wants 16 kHz mono audio.
        speech16 = out_lipsync.parent / "speech_16k.wav"
        run_ffmpeg(["-y", "-i", str(speech), "-ar", "16000", "-ac", "1", str(speech16)])
        mt_out = out_lipsync.parent / "mt_out"
        run_in_env(
            settings.ENV_MT,
            [
                "python",
                f"{settings.RUNNERS_DIR}/run_musetalk.py",
                "--video",
                str(animated),
                "--audio",
                str(speech16),
                "--result-dir",
                str(mt_out),
                "--bbox-shift",
                str(settings.MUSETALK_BBOX_SHIFT),
            ],
            cwd=f"{settings.AI_ROOT}/MuseTalk",
        )
        results = glob.glob(f"{mt_out}/**/*.mp4", recursive=True)
        if not results:
            raise RuntimeError(f"MuseTalk produced no output in {mt_out}")
        shutil.copyfile(results[-1], out_lipsync)
