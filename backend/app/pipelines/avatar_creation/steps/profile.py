"""Stage 6 + 8: head-pose statistics, checksum, and profile.json assembly."""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from app.pipelines.avatar_creation.ml.backends import (
    F5_VERSION,
    INSIGHTFACE_MODEL,
    LIVEPORTRAIT_VERSION,
    MUSETALK_TARGET,
)

SCHEMA_VERSION = "1.0"


def head_pose_stats(pose_samples: list) -> dict:
    """Compute yaw/pitch/roll mean+std from [yaw,pitch,roll] samples."""
    axes = ("yaw", "pitch", "roll")
    out: dict = {"n_frames": len(pose_samples)}
    for i, axis in enumerate(axes):
        vals = [float(s[i]) for s in pose_samples if s is not None and len(s) > i]
        if vals:
            out[axis] = {
                "mean": round(statistics.fmean(vals), 3),
                "std": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
            }
        else:
            out[axis] = {"mean": 0.0, "std": 0.0}
    return out


def compute_checksum(paths: list[Path]) -> str:
    """SHA-256 over the concatenated bytes of the key avatar artifacts."""
    h = hashlib.sha256()
    for p in paths:
        if p and Path(p).exists():
            h.update(Path(p).read_bytes())
    return f"sha256:{h.hexdigest()}"


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def assemble_profile(
    *,
    avatar_id: int,
    user_id: int,
    voice_model_id: int,
    face_meta: dict,
    pose_stats: dict,
    motion_meta: dict,
    ref_meta: dict,
    voice_meta: dict,
    video_meta: dict,
    artifact_paths: dict,
) -> dict:
    """Build the canonical profile.json (AVATAR_CREATION_PIPELINE.md §7)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "avatar_id": str(avatar_id),
        "user_id": str(user_id),
        "status": "ready",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "face": {
            "reference_frame": artifact_paths["face"],
            "thumbnail": artifact_paths["thumbnail"],
            "bbox": face_meta.get("bbox"),
            "crop_size": face_meta.get("crop_size", [512, 512]),
            "quality_score": face_meta.get("quality_score"),
        },
        "head_pose_stats": pose_stats,
        "motion_template": {
            "path": artifact_paths["motion_template"],
            "model": motion_meta.get("model", LIVEPORTRAIT_VERSION),
        },
        "voice_model": {
            "voice_model_id": str(voice_model_id),
            "path": artifact_paths["voice_model"],
            "reference": artifact_paths["reference"],
            "model": voice_meta.get("model_version", F5_VERSION),
        },
        "source_video": {
            "video_id": str(video_meta.get("video_id")),
            "path": artifact_paths["source_video"],
            "duration_s": video_meta.get("duration_seconds"),
            "resolution": [video_meta.get("width"), video_meta.get("height")],
            "codec": video_meta.get("codec"),
        },
        "model_versions": {
            "f5_tts": F5_VERSION,
            "liveportrait": LIVEPORTRAIT_VERSION,
            "insightface": INSIGHTFACE_MODEL,
            "musetalk_target": MUSETALK_TARGET,
        },
        "checksum": compute_checksum(
            [
                Path(artifact_paths["_face_abs"]),
                Path(artifact_paths["_motion_abs"]),
                Path(artifact_paths["_reference_abs"]),
                Path(artifact_paths["_voice_model_abs"]),
            ]
        ),
    }
