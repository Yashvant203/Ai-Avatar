"""Avatar CRUD, script generation, upload validation, and owner-scoping tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.routers.avatars as avatars_router


def _register(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post(
        "/api/auth/signup", json={"email": email, "password": "password123", "full_name": "T"}
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_list_get_delete_avatar(client: TestClient) -> None:
    h = _register(client, "owner@example.com")

    created = client.post("/api/avatars", json={"name": "My Avatar"}, headers=h)
    assert created.status_code == 201
    avatar = created.json()
    assert avatar["status"] == "pending"
    aid = avatar["id"]

    listed = client.get("/api/avatars", headers=h)
    assert listed.status_code == 200
    assert [a["id"] for a in listed.json()] == [aid]

    got = client.get(f"/api/avatars/{aid}", headers=h)
    assert got.status_code == 200 and got.json()["name"] == "My Avatar"

    deleted = client.delete(f"/api/avatars/{aid}", headers=h)
    assert deleted.status_code == 204
    assert client.get(f"/api/avatars/{aid}", headers=h).status_code == 404


def test_delete_avatar_with_children_cascades(client: TestClient, db_session) -> None:
    """Deleting an avatar that already has a voice_model + generation_job (and a
    generated_video) must succeed — the DB cascades the NOT NULL children."""
    from app.models.avatar import Avatar
    from app.models.enums import JobStatus, VoiceStatus
    from app.models.generated_video import GeneratedVideo
    from app.models.generation_job import GenerationJob
    from app.models.training_video import TrainingVideo
    from app.models.voice_model import VoiceModel

    h = _register(client, "cascade@example.com")
    aid = client.post("/api/avatars", json={"name": "Rich"}, headers=h).json()["id"]
    avatar = db_session.get(Avatar, aid)
    uid = avatar.user_id

    # Attach the children that previously broke deletion.
    db_session.add(VoiceModel(avatar_id=aid, status=VoiceStatus.ready))
    tv = TrainingVideo(user_id=uid, avatar_id=aid, file_path="/tmp/x.mp4")
    db_session.add(tv)
    job = GenerationJob(user_id=uid, avatar_id=aid, script_text="hi", status=JobStatus.completed)
    db_session.add(job)
    db_session.flush()
    db_session.add(GeneratedVideo(job_id=job.id, avatar_id=aid, file_path="/tmp/o.mp4"))
    db_session.commit()

    # Delete should now succeed (was IntegrityError before the fix).
    assert client.delete(f"/api/avatars/{aid}", headers=h).status_code == 204
    assert client.get(f"/api/avatars/{aid}", headers=h).status_code == 404

    # Owned children are gone; the user's recording survives with avatar_id NULL.
    assert db_session.query(VoiceModel).filter_by(avatar_id=aid).count() == 0
    assert db_session.query(GenerationJob).filter_by(avatar_id=aid).count() == 0
    assert db_session.query(GeneratedVideo).filter_by(avatar_id=aid).count() == 0
    db_session.refresh(tv)
    assert tv.avatar_id is None


def test_avatar_requires_auth(client: TestClient) -> None:
    assert client.get("/api/avatars").status_code == 401
    assert client.post("/api/avatars", json={"name": "x"}).status_code == 401


def test_owner_scoping(client: TestClient) -> None:
    ha = _register(client, "a@example.com")
    hb = _register(client, "b@example.com")
    aid = client.post("/api/avatars", json={"name": "A"}, headers=ha).json()["id"]

    # User B cannot see or delete user A's avatar — 404, no existence leak.
    assert client.get(f"/api/avatars/{aid}", headers=hb).status_code == 404
    assert client.delete(f"/api/avatars/{aid}", headers=hb).status_code == 404
    assert client.get(f"/api/avatars/{aid}", headers=ha).status_code == 200


def test_generate_and_get_script(client: TestClient) -> None:
    h = _register(client, "script@example.com")
    aid = client.post("/api/avatars", json={"name": "S"}, headers=h).json()["id"]

    gen = client.post(f"/api/avatars/{aid}/script", headers=h)
    assert gen.status_code == 201
    script = gen.json()
    assert script["word_count"] > 100
    assert script["avatar_id"] == aid

    got = client.get(f"/api/avatars/{aid}/script", headers=h)
    assert got.status_code == 200 and got.json()["id"] == script["id"]


def test_get_script_404_when_none(client: TestClient) -> None:
    h = _register(client, "noscript@example.com")
    aid = client.post("/api/avatars", json={"name": "N"}, headers=h).json()["id"]
    assert client.get(f"/api/avatars/{aid}/script", headers=h).status_code == 404


def test_upload_rejects_bad_type(client: TestClient) -> None:
    h = _register(client, "badtype@example.com")
    aid = client.post("/api/avatars", json={"name": "U"}, headers=h).json()["id"]
    resp = client.post(
        f"/api/avatars/{aid}/video",
        headers=h,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_oversize(client: TestClient, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)  # any non-empty file is too big
    h = _register(client, "big@example.com")
    aid = client.post("/api/avatars", json={"name": "U"}, headers=h).json()["id"]
    resp = client.post(
        f"/api/avatars/{aid}/video",
        headers=h,
        files={"file": ("clip.mp4", b"x" * 2048, "video/mp4")},
    )
    assert resp.status_code == 413


def test_upload_accepted_schedules_pipeline(client: TestClient, monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(avatars_router, "run_avatar_pipeline", lambda aid: calls.append(aid))

    h = _register(client, "upload@example.com")
    aid = client.post("/api/avatars", json={"name": "U"}, headers=h).json()["id"]
    client.post(f"/api/avatars/{aid}/script", headers=h)

    resp = client.post(
        f"/api/avatars/{aid}/video",
        headers=h,
        files={"file": ("clip.mp4", b"fake-mp4-bytes" * 100, "video/mp4")},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "uploaded"
    assert calls == [aid]  # pipeline scheduled exactly once


def test_status_endpoint(client: TestClient) -> None:
    h = _register(client, "status@example.com")
    aid = client.post("/api/avatars", json={"name": "St"}, headers=h).json()["id"]
    resp = client.get(f"/api/avatars/{aid}/status", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["avatar_id"] == aid
    assert body["status"] == "pending"
    assert body["video"] is None
