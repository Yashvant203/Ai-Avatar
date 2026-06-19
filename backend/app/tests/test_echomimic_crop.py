"""Pure crop-geometry for EchoMimic reference preparation.

The geometry functions take no torch/cv2 dependency so they're unit-testable;
the MTCNN detection + PIL I/O wrapper around them runs only in envEM (pragma).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_RUNNER = (
    Path(__file__).resolve().parents[3] / "ml_models" / "runners" / "echomimic_generate.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("echomimic_generate", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


em = _load()


def test_halfbody_crop_box_centered() -> None:
    # face fh=160, cx=500 -> side=5*160=800, top=200-0.6*160=104, left=500-400=100
    assert em._halfbody_crop_box(1000, 1000, (450, 200, 550, 360)) == (100, 104, 900, 904)


def test_halfbody_crop_box_returns_negative_for_padding() -> None:
    # face high in frame -> top goes negative; caller pads (no clamping here)
    assert em._halfbody_crop_box(1080, 1920, (450, 20, 550, 120)) == (250, -40, 750, 460)


def test_halfbody_crop_box_is_always_square() -> None:
    left, top, right, bottom = em._halfbody_crop_box(1280, 720, (600, 100, 700, 250))
    assert (right - left) == (bottom - top)


def test_pad_square_box_landscape() -> None:
    # 1920x1080 -> side 1920, centered vertically (short axis padded)
    assert em._pad_square_box(1920, 1080) == (0, -420, 1920, 1500)


def test_pad_square_box_portrait() -> None:
    # 1080x1920 -> side 1920, centered horizontally
    assert em._pad_square_box(1080, 1920) == (-420, 0, 1500, 1920)
