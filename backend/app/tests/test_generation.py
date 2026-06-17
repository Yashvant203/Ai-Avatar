"""Generation: queue claim/reaper, HTTP validation, end-to-end stub render, download auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.paths as paths
import app.pipelines.generation.ml.loaders as gen_loaders
from app.core.config import settings
from app.db.base import Base
from app.models.avatar import Avatar
from app.models.enums import AvatarStatus, JobStatus
from app.models.user import User
from app.queue import db_queue


# --------------------------------------------------------------------------- #
# Queue unit tests (own engine, no HTTP)
# --------------------------------------------------------------------------- #
@pytest.fixture
def gen_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield SessionLocal
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed_ready_avatar(db) -> tuple[int, int]:
    user = User(email="g@example.com", hashed_password="h", is_active=True)
    db.add(user)
    db.flush()
    avatar = Avatar(user_id=user.id, name="A", status=AvatarStatus.ready)
    db.add(avatar)
    db.commit()
    return user.id, avatar.id


def test_claim_is_exclusive(gen_db) -> None:
    db = gen_db()
    uid, aid = _seed_ready_avatar(db)
    db_queue.enqueue_job(db, user_id=uid, avatar_id=aid, script_text="hi")

    first = db_queue.claim_next_job(db)
    assert first is not None and first.status == JobStatus.processing
    # No more queued jobs → second claim returns None.
    assert db_queue.claim_next_job(db) is None
    db.close()


def test_reaper_requeues_zombie(gen_db, monkeypatch) -> None:
    monkeypatch.setattr(settings, "JOB_HEARTBEAT_TIMEOUT", 60)
    db = gen_db()
    uid, aid = _seed_ready_avatar(db)
    job = db_queue.enqueue_job(db, user_id=uid, avatar_id=aid, script_text="hi")
    db_queue.claim_next_job(db)
    # Backdate the heartbeat well past the timeout.
    job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db.commit()

    assert db_queue.requeue_zombie_jobs(db) == 1
    db.refresh(job)
    assert job.status == JobStatus.queued
    assert job.started_at is None
    db.close()


# --------------------------------------------------------------------------- #
# HTTP tests (shared client fixture)
# --------------------------------------------------------------------------- #
def _register(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/auth/signup", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ready_avatar(client: TestClient, db_session, headers) -> int:
    aid = client.post("/api/avatars", json={"name": "Gen"}, headers=headers).json()["id"]
    avatar = db_session.get(Avatar, aid)
    avatar.status = AvatarStatus.ready
    db_session.commit()
    return aid


def test_generate_requires_ready_avatar(client: TestClient, db_session) -> None:
    h = _register(client, "nr@example.com")
    aid = client.post("/api/avatars", json={"name": "P"}, headers=h).json()["id"]  # pending
    resp = client.post("/api/generate", json={"avatar_id": aid, "script_text": "hello"}, headers=h)
    assert resp.status_code == 409  # not ready


def test_generate_enqueues_job(client: TestClient, db_session) -> None:
    h = _register(client, "gen@example.com")
    aid = _ready_avatar(client, db_session, h)
    resp = client.post(
        "/api/generate", json={"avatar_id": aid, "script_text": "hello world"}, headers=h
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["estimated_duration_s"] > 0

    jid = body["job_id"]
    poll = client.get(f"/api/jobs/{jid}", headers=h)
    assert poll.status_code == 200 and poll.json()["progress"] == 0


def test_generate_rejects_foreign_avatar(client: TestClient, db_session) -> None:
    ha = _register(client, "ga@example.com")
    hb = _register(client, "gb@example.com")
    aid = _ready_avatar(client, db_session, ha)
    resp = client.post("/api/generate", json={"avatar_id": aid, "script_text": "x"}, headers=hb)
    assert resp.status_code == 404


def test_job_and_video_owner_scoping(client: TestClient, db_session) -> None:
    ha = _register(client, "ya@example.com")
    hb = _register(client, "yb@example.com")
    aid = _ready_avatar(client, db_session, ha)
    jid = client.post(
        "/api/generate", json={"avatar_id": aid, "script_text": "x"}, headers=ha
    ).json()["job_id"]
    assert client.get(f"/api/jobs/{jid}", headers=hb).status_code == 404
    assert client.get(f"/api/jobs/{jid}", headers=ha).status_code == 200


def test_cancel_queued_job(client: TestClient, db_session) -> None:
    h = _register(client, "cancel@example.com")
    aid = _ready_avatar(client, db_session, h)
    jid = client.post(
        "/api/generate", json={"avatar_id": aid, "script_text": "x"}, headers=h
    ).json()["job_id"]
    resp = client.post(f"/api/jobs/{jid}/cancel", headers=h)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"


def test_download_404_for_missing_video(client: TestClient, db_session) -> None:
    h = _register(client, "dl@example.com")
    assert client.get("/api/videos/999/download", headers=h).status_code == 404


def _seed_completed_video(db_session, user_id: int, avatar_id: int) -> int:
    from app.models.generated_video import GeneratedVideo
    from app.models.generation_job import GenerationJob

    job = GenerationJob(
        user_id=user_id, avatar_id=avatar_id, script_text="x", status=JobStatus.completed
    )
    db_session.add(job)
    db_session.flush()
    video = GeneratedVideo(
        job_id=job.id, avatar_id=avatar_id, file_path="/tmp/none.mp4", resolution="512x512"
    )
    db_session.add(video)
    db_session.commit()
    return video.id


def test_list_videos_is_owner_scoped(client: TestClient, db_session) -> None:
    ha = _register(client, "va@example.com")
    hb = _register(client, "vb@example.com")
    aid = _ready_avatar(client, db_session, ha)
    a_user = db_session.get(Avatar, aid).user_id
    vid = _seed_completed_video(db_session, a_user, aid)

    mine = client.get("/api/videos", headers=ha)
    assert mine.status_code == 200
    assert [v["id"] for v in mine.json()] == [vid]
    # Other user sees none.
    assert client.get("/api/videos", headers=hb).json() == []


# --------------------------------------------------------------------------- #
# End-to-end render via the stub backend (real ffmpeg → playable mp4)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="ffmpeg required")
def test_orchestrator_produces_downloadable_mp4(
    gen_db, client, db_session, tmp_path, monkeypatch
) -> None:
    from app.pipelines.generation.orchestrator import run_generation_job

    monkeypatch.setattr(settings, "PIPELINE_BACKEND", "stub")
    monkeypatch.setattr(settings, "WORDS_PER_SECOND", 50.0)  # keep the clip short
    gen_loaders.get_generation_backend.cache_clear()

    db = gen_db()
    uid, aid = _seed_ready_avatar(db)
    db_queue.enqueue_job(db, user_id=uid, avatar_id=aid, script_text="hello world " * 5)
    claimed = db_queue.claim_next_job(db)
    assert claimed is not None

    video = run_generation_job(db, claimed)
    assert video is not None

    db.refresh(claimed)
    assert claimed.status == JobStatus.completed
    assert claimed.progress == 100
    assert claimed.output_video_id == video.id

    out = paths.output_video_final_path(claimed.id)
    assert out.exists() and out.stat().st_size > 0
    assert paths.output_thumb_path(claimed.id).exists()
    # frames/ cleaned up on success
    assert not paths.output_frames_dir(claimed.id).exists()

    assert video.file_size_bytes and video.file_size_bytes > 0
    assert video.resolution == "512x512"
    db.close()
