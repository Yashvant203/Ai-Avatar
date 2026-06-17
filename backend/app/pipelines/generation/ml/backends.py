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
from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg

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
        self, out_animated: Path, *, face: Path | None, duration_s: float, fps: int
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
        self, out_animated: Path, *, face: Path | None, duration_s: float, fps: int
    ) -> None:
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
    """Production stages with lazy heavy imports."""

    name = "real"

    @staticmethod
    def is_available() -> bool:
        import importlib.util

        return all(importlib.util.find_spec(m) is not None for m in ("torch", "f5_tts", "musetalk"))

    def synthesize_speech(
        self, out_speech: Path, *, script_text: str, voice_ref: Path | None, duration_s: float
    ) -> float:  # pragma: no cover - requires ML stack
        import torch  # noqa: F401
        import torchaudio
        from f5_tts.api import F5TTS

        engine = F5TTS(model=F5_VERSION, device="cuda")
        wav, sr = engine.infer(ref_audio=str(voice_ref), gen_text=script_text)
        torchaudio.save(str(out_speech), wav, sr)
        return wav.shape[-1] / sr

    def animate(
        self, out_animated: Path, *, face: Path | None, duration_s: float, fps: int
    ) -> None:  # pragma: no cover - requires ML stack
        raise NotImplementedError("LivePortrait driving — see VIDEO_GENERATION_PIPELINE.md §4")

    def lipsync(
        self, animated: Path, speech: Path, out_lipsync: Path
    ) -> None:  # pragma: no cover - requires ML stack
        raise NotImplementedError("MuseTalk lip-sync — see VIDEO_GENERATION_PIPELINE.md §4")
