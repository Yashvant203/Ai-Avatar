"""Stage → progress-band mapping (VIDEO_GENERATION_PIPELINE.md §7)."""

from __future__ import annotations

# (start, end) percentage bands; monotonic and meaningful to the UI.
BANDS: dict[str, tuple[int, int]] = {
    "claimed": (1, 1),
    "f5_tts": (5, 30),
    "liveportrait": (30, 60),
    "musetalk": (60, 85),
    "mux": (85, 98),
    "finalized": (100, 100),
}


def band_start(stage: str) -> int:
    return BANDS[stage][0]


def band_end(stage: str) -> int:
    return BANDS[stage][1]


def within(stage: str, fraction: float) -> int:
    """Map a 0..1 fraction within a stage to an absolute percentage."""
    start, end = BANDS[stage]
    fraction = max(0.0, min(1.0, fraction))
    return int(start + (end - start) * fraction)
