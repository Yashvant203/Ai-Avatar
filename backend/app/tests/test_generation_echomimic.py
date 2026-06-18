"""StubBackend.generate_video produces a real, playable MP4 (echomimic engine path)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from app.pipelines.avatar_creation.ml.ffmpeg import ffprobe_metadata
from app.pipelines.generation.ml.backends import StubBackend

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required",
)


def _make_audio(path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=2:sample_rate=24000", "-ac", "1", str(path)],
        check=True,
    )


def _make_image(path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "color=c=blue:s=320x320:d=1", "-frames:v", "1", str(path)],
        check=True,
    )


def test_stub_generate_video_makes_playable_mp4(tmp_path) -> None:
    audio = tmp_path / "speech.wav"
    ref = tmp_path / "ref.png"
    out = tmp_path / "out.mp4"
    _make_audio(audio)
    _make_image(ref)

    StubBackend().generate_video(
        reference_image=ref, audio=audio, out_video=out, duration_s=2.0, fps=25
    )

    assert out.exists() and out.stat().st_size > 0
    meta = ffprobe_metadata(out)
    assert meta.get("duration_seconds") and meta["duration_seconds"] > 1.0
