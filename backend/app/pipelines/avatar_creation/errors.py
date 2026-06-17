"""Pipeline error taxonomy (AVATAR_CREATION_PIPELINE.md §9)."""

from __future__ import annotations

# Error codes that indicate a bad *input video* (so the training_video is also
# marked failed, not just the avatar).
VIDEO_INPUT_ERRORS = frozenset(
    {
        "INVALID_FILE",
        "DURATION_OUT_OF_RANGE",
        "NO_FACE_DETECTED",
        "MULTIPLE_FACES",
        "LOW_FACE_QUALITY",
    }
)


class PipelineError(Exception):
    """A pipeline-stage failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
