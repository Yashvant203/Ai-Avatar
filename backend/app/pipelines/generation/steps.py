"""Shared generation steps: duration estimate + ffmpeg mux/thumbnail (Stage 4)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.pipelines.avatar_creation.ml.ffmpeg import ffprobe_metadata, run_ffmpeg


def estimate_duration_seconds(script_text: str) -> float:
    """Estimate spoken length from word count (used for ETA + stub audio length)."""
    words = max(1, len(script_text.split()))
    return max(1.0, words / settings.WORDS_PER_SECOND)


def mux_output(lipsync: Path, speech: Path, out_video: Path, *, fps: int) -> None:
    """Mux lip-synced video + speech into the final H.264/AAC MP4 (faststart)."""
    out_video.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(lipsync),
            "-i",
            str(speech),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_video),
        ]
    )


def make_thumbnail(out_video: Path, thumb: Path) -> None:
    """Grab a poster frame ~1s in, clamped to within the clip (handles short clips)."""
    meta = ffprobe_metadata(out_video)
    dur = meta.get("duration_seconds") or 0.0
    ts = min(1.0, dur * 0.5) if dur else 0.0
    run_ffmpeg(
        ["-y", "-ss", f"{ts:.3f}", "-i", str(out_video), "-frames:v", "1", "-q:v", "3", str(thumb)]
    )


def probe_output(out_video: Path) -> dict:
    return ffprobe_metadata(out_video)
