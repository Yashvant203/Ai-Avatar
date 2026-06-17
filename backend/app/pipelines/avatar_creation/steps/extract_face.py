"""Stage 5: sample frames and select the best reference face."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.ml.ffmpeg import FFmpegError, run_ffmpeg


def sample_frames(video_path: str | Path, frame_dir: Path, *, fps: int = 2) -> Path:
    """Sample frames at `fps` into frame_dir (cleared first). Returns frame_dir."""
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(video_path),
                "-vf",
                f"fps={fps},scale=-1:720",
                "-q:v",
                "2",
                str(frame_dir / "f_%05d.jpg"),
            ]
        )
    except FFmpegError as exc:
        raise PipelineError("INVALID_FILE", f"frame sampling failed: {exc}") from exc
    if not any(frame_dir.glob("*.jpg")):
        raise PipelineError("NO_FACE_DETECTED", "no frames produced from video")
    return frame_dir
