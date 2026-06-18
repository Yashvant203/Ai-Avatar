"""End-to-end avatar-creation pipeline test using the stub backend.

A real synthetic video (ffmpeg lavfi testsrc + sine) is fed through the full
runner. ffmpeg audio/frame extraction runs for real; the stub backend supplies
the ML-heavy steps. We assert the state machine reaches `ready` and the
documented artifacts + profile.json contract are produced.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.paths as paths
import app.pipelines.avatar_creation.ml.loaders as loaders
from app.core.config import settings
from app.db.base import Base
from app.models.avatar import Avatar
from app.models.enums import AvatarStatus, VideoStatus, VoiceStatus
from app.models.training_script import TrainingScript
from app.models.training_video import TrainingVideo
from app.models.user import User
from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.runner import run_avatar_pipeline

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required",
)


def _make_video(path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=3",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )


@pytest.fixture
def pipeline_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield TestingSessionLocal
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(SessionLocal, video_path) -> int:
    db = SessionLocal()
    user = User(email="p@example.com", hashed_password="h", is_active=True)
    db.add(user)
    db.flush()
    avatar = Avatar(user_id=user.id, name="Pipe", status=AvatarStatus.pending)
    db.add(avatar)
    db.flush()
    db.add(
        TrainingScript(
            user_id=user.id, avatar_id=avatar.id, content="hello world " * 50, word_count=100
        )
    )
    db.add(
        TrainingVideo(
            user_id=user.id,
            avatar_id=avatar.id,
            file_path=str(video_path),
            status=VideoStatus.uploaded,
        )
    )
    db.commit()
    aid = avatar.id
    db.close()
    return aid


def test_pipeline_reaches_ready(pipeline_db, tmp_path, monkeypatch) -> None:
    # Relax duration bounds for the short synthetic clip; force stub backend.
    monkeypatch.setattr(settings, "MIN_VIDEO_SECONDS", 1.0)
    monkeypatch.setattr(settings, "MAX_VIDEO_SECONDS", 600.0)
    monkeypatch.setattr(settings, "PIPELINE_BACKEND", "stub")
    loaders.get_backend.cache_clear()

    video_path = tmp_path / "src.mp4"
    _make_video(video_path)
    aid = _seed(pipeline_db, video_path)

    run_avatar_pipeline(aid, db_factory=pipeline_db)

    db = pipeline_db()
    avatar = db.get(Avatar, aid)
    assert avatar.status == AvatarStatus.ready
    assert avatar.error_message is None
    assert avatar.voice_model_id is not None
    assert avatar.source_video_id is not None

    video = db.query(TrainingVideo).filter_by(avatar_id=aid).one()
    assert video.status == VideoStatus.analyzed
    assert video.duration_seconds and video.duration_seconds > 0

    voice = avatar.voice_model
    assert voice is not None and voice.status == VoiceStatus.ready
    db.close()

    # Artifacts on disk under the redirected storage root.
    adir = paths.avatar_dir(aid)
    vdir = paths.voice_dir(aid)
    for f in ("profile.json", "face.png", "thumbnail.png", "driving.mp4", "reference_halfbody.png"):
        assert (adir / f).exists(), f"missing {f}"
    for f in ("source_audio.wav", "reference.wav", "model.pt"):
        assert (vdir / f).exists(), f"missing {f}"

    # profile.json contract.
    prof = json.loads((adir / "profile.json").read_text())
    assert prof["schema_version"] == "1.0"
    assert prof["status"] == "ready"
    assert prof["checksum"].startswith("sha256:")
    assert prof["voice_model"]["voice_model_id"]
    assert prof["face"]["reference_frame"].endswith("face.png")
    assert set(prof["model_versions"]) == {
        "f5_tts",
        "liveportrait",
        "insightface",
        "musetalk_target",
    }


def test_pipeline_marks_failed_on_invalid_video(pipeline_db, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PIPELINE_BACKEND", "stub")
    loaders.get_backend.cache_clear()

    bad = tmp_path / "not_a_video.mp4"
    bad.write_text("this is not a video")
    aid = _seed(pipeline_db, bad)

    with pytest.raises(PipelineError):
        run_avatar_pipeline(aid, db_factory=pipeline_db)

    db = pipeline_db()
    avatar = db.get(Avatar, aid)
    assert avatar.status == AvatarStatus.failed
    assert avatar.error_message == "INVALID_FILE"
    video = db.query(TrainingVideo).filter_by(avatar_id=aid).one()
    assert video.status == VideoStatus.failed
    db.close()
