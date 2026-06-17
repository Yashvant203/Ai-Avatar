"""Stage 1 + duration validation: extract a clean mono 24 kHz reference track."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.ml.ffmpeg import FFmpegError, ffprobe_metadata, run_ffmpeg

# Documented filter chain (AVATAR_CREATION_PIPELINE.md §4): trim rumble/hiss,
# EBU R128 loudness normalize, then remove long silences.
_AUDIO_FILTER = (
    "highpass=f=80,lowpass=f=8000,"
    "loudnorm=I=-23:LRA=7:TP=-2,"
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.3:"
    "stop_periods=-1:stop_threshold=-45dB:stop_silence=0.5"
)


def probe_video(video_path: str | Path) -> dict:
    """ffprobe the upload; raise INVALID_FILE / DURATION_OUT_OF_RANGE as needed."""
    try:
        meta = ffprobe_metadata(video_path)
    except FFmpegError as exc:
        raise PipelineError("INVALID_FILE", f"cannot read video: {exc}") from exc

    duration = meta.get("duration_seconds")
    if duration is None:
        raise PipelineError("INVALID_FILE", "missing duration / not a video")
    if not (settings.MIN_VIDEO_SECONDS <= duration <= settings.MAX_VIDEO_SECONDS):
        raise PipelineError(
            "DURATION_OUT_OF_RANGE",
            f"duration {duration:.1f}s outside "
            f"[{settings.MIN_VIDEO_SECONDS:.0f}, {settings.MAX_VIDEO_SECONDS:.0f}]s",
        )
    return meta


def extract_source_audio(video_path: str | Path, out_wav: Path) -> None:
    """Extract normalized mono 24 kHz PCM from the video."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-sample_fmt",
                "s16",
                "-af",
                _AUDIO_FILTER,
                str(out_wav),
            ]
        )
    except FFmpegError as exc:
        raise PipelineError("AUDIO_EXTRACT_FAILED", str(exc)) from exc
    if not out_wav.exists() or out_wav.stat().st_size == 0:
        raise PipelineError("AUDIO_LOW_QUALITY", "extracted audio is empty")
