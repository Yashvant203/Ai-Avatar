"""Safe ffmpeg/ffprobe subprocess wrappers.

Security & robustness (roadmap Phase 3 risks):
- Always call with an ARGUMENT LIST (never a shell string, never shell=True).
- Always pass a hard timeout so a hung encode cannot block a worker forever.
- Paths are passed as args, so spaces/special chars cannot inject commands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("pipeline.ffmpeg")

DEFAULT_TIMEOUT = 300  # seconds


class FFmpegError(Exception):
    """Raised on ffmpeg/ffprobe failure or timeout."""


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise FFmpegError(f"{tool} not found on PATH (run ml_models/setup_ffmpeg.sh)")
    return path


def run_ffmpeg(args: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Run `ffmpeg <args>` with -hide_banner -nostdin. Raises FFmpegError on failure."""
    cmd = [_require("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", *args]
    logger.debug("ffmpeg %s", " ".join(args))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()[:500]}")


def ffprobe_metadata(path: str | Path, *, timeout: int = 30) -> dict:
    """Return {duration_seconds, width, height, codec} for a media file."""
    cmd = [
        _require("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffprobe timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {proc.stderr.strip()[:500]}")

    data = json.loads(proc.stdout or "{}")
    fmt = data.get("format", {})
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = fmt.get("duration") or video_stream.get("duration")
    return {
        "duration_seconds": float(duration) if duration else None,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "codec": video_stream.get("codec_name"),
    }
