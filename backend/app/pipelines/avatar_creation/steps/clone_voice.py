"""Stage 4: build the F5-TTS voice model artifact and update the voice_models row.

F5-TTS is zero-shot/reference-based — "training" here means validating and
persisting the reference + conditioning artifact, not fine-tuning weights
(AVATAR_CREATION_PIPELINE.md §5).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.enums import VoiceStatus
from app.models.voice_model import VoiceModel
from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.ml.backends import AvatarBackend


def build_voice_model(
    db: Session,
    *,
    voice: VoiceModel,
    backend: AvatarBackend,
    reference: Path,
    transcript: str,
    out_model: Path,
    sample_rate: int = 24000,
) -> dict:
    voice.status = VoiceStatus.training
    db.commit()
    try:
        meta = backend.build_voice_model(reference, transcript, out_model, sample_rate=sample_rate)
    except PipelineError as exc:
        voice.status = VoiceStatus.failed
        voice.error_message = exc.code
        db.commit()
        raise
    except Exception as exc:
        voice.status = VoiceStatus.failed
        voice.error_message = str(exc)[:500]
        db.commit()
        raise

    voice.model_path = meta["model_path"]
    voice.reference_audio_path = str(reference)
    voice.sample_rate = sample_rate
    voice.status = VoiceStatus.ready
    db.commit()
    return meta
