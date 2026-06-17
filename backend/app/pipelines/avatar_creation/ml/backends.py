"""ML backend abstraction for the avatar-creation pipeline.

Two implementations satisfy the same interface:

- RealBackend: lazily imports torch / torchaudio / insightface / f5_tts and runs
  the production code described in AVATAR_CREATION_PIPELINE.md (§4–§7). Requires
  a GPU and the model weights under ml_models/weights/.
- StubBackend: uses only ffmpeg + the standard library to produce VALID
  placeholder artifacts with the correct shapes/paths, so the full pipeline,
  state machine, and profile.json contract run and can be tested without a GPU.

`loaders.get_backend()` picks the backend from settings.PIPELINE_BACKEND
("auto" → real if importable, else stub).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Protocol

from app.core.logging import get_logger
from app.pipelines.avatar_creation.errors import PipelineError
from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg

logger = get_logger("pipeline.backend")

F5_VERSION = "f5-tts-base-v1"
LIVEPORTRAIT_VERSION = "liveportrait-v1"
INSIGHTFACE_MODEL = "buffalo_l"
MUSETALK_TARGET = "musetalk-v1"


class AvatarBackend(Protocol):
    name: str

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict: ...

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict: ...

    def select_best_face(self, frame_dir: Path, out_face: Path, out_thumb: Path) -> dict: ...

    def prep_appearance(self, face: Path, out_template: Path) -> dict: ...


# --------------------------------------------------------------------------- #
# Stub backend — ffmpeg + stdlib only
# --------------------------------------------------------------------------- #
class StubBackend:
    """Deterministic, GPU-free backend producing valid placeholder artifacts."""

    name = "stub"

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict:
        # Take up to the first 15s as the reference clip.
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(source_audio),
                "-t",
                "15",
                "-ac",
                "1",
                "-ar",
                "24000",
                str(out_reference),
            ]
        )
        transcript = " ".join((script_text or "reference audio sample").split()[:40])
        return {
            "reference_path": str(out_reference),
            "transcript": transcript,
            "qc": {"snr_db": None, "clip_ratio": None, "stub": True},
            "duration_s": 15.0,
        }

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict:
        # F5-TTS is reference-based; the artifact is a small profile, not weights.
        artifact = {
            "kind": "f5tts_voice_profile",
            "backend": "stub",
            "model_version": F5_VERSION,
            "sample_rate": sample_rate,
            "reference_path": str(reference),
            "reference_text": transcript,
        }
        with out_model.open("wb") as fh:
            pickle.dump(artifact, fh)
        return {"model_path": str(out_model), "model_version": F5_VERSION}

    def select_best_face(self, frame_dir: Path, out_face: Path, out_thumb: Path) -> dict:
        frames = sorted(frame_dir.glob("*.jpg"))
        if not frames:
            raise PipelineError("NO_FACE_DETECTED", "no frames sampled from video")
        # Use the middle frame; scale to the documented sizes via ffmpeg.
        chosen = frames[len(frames) // 2]
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=512:512", str(out_face)])
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=256:256", str(out_thumb)])
        return {
            "bbox": [0, 0, 512, 512],
            "crop_size": [512, 512],
            "quality_score": 0.5,
            "pose_samples": [],
        }

    def prep_appearance(self, face: Path, out_template: Path) -> dict:
        template = {
            "kind": "liveportrait_appearance",
            "backend": "stub",
            "model_version": LIVEPORTRAIT_VERSION,
            "source_face": str(face),
        }
        with out_template.open("wb") as fh:
            pickle.dump(template, fh)
        return {"path": str(out_template), "model": LIVEPORTRAIT_VERSION}


# --------------------------------------------------------------------------- #
# Real backend — lazy heavy imports (production path)
# --------------------------------------------------------------------------- #
class RealBackend:
    """Production backend. Heavy libs are imported lazily inside methods so that
    importing this module never pulls in torch/insightface on the API process."""

    name = "real"

    @staticmethod
    def is_available() -> bool:
        import importlib.util

        return all(
            importlib.util.find_spec(m) is not None for m in ("torch", "torchaudio", "insightface")
        )

    def select_reference(
        self, source_audio: Path, out_reference: Path, *, script_text: str | None
    ) -> dict:  # pragma: no cover - requires ML stack
        import numpy as np
        import torchaudio

        wav, sr = torchaudio.load(str(source_audio))
        if sr != 24000:
            wav = torchaudio.functional.resample(wav, sr, 24000)
            sr = 24000
        win = int(15 * sr)
        x = wav.squeeze().numpy()
        # Pick the highest-energy contiguous 15s window as a robust reference.
        best_start, best_energy = 0, -1.0
        for start in range(0, max(1, len(x) - win), int(2 * sr)):
            energy = float(np.sqrt(np.mean(x[start : start + win] ** 2) + 1e-9))
            if energy > best_energy:
                best_start, best_energy = start, energy
        seg = wav[:, best_start : best_start + win]
        torchaudio.save(str(out_reference), seg, sr)
        transcript = " ".join((script_text or "").split()[:40])
        return {
            "reference_path": str(out_reference),
            "transcript": transcript,
            "qc": {"energy": best_energy},
            "duration_s": seg.shape[1] / sr,
        }

    def build_voice_model(
        self, reference: Path, transcript: str, out_model: Path, *, sample_rate: int
    ) -> dict:  # pragma: no cover - requires ML stack
        import torch
        import torchaudio
        from f5_tts.api import F5TTS

        ref_wav, sr = torchaudio.load(str(reference))
        try:
            engine = F5TTS(model=F5_VERSION, device="cuda")
            ref_embedding = engine.encode_reference(ref_wav, sr, transcript)
            artifact = {
                "kind": "f5tts_voice_profile",
                "model_version": F5_VERSION,
                "sample_rate": sr,
                "reference_path": str(reference),
                "reference_text": transcript,
                "ref_embedding": ref_embedding.cpu(),
            }
            torch.save(artifact, str(out_model))
        except torch.cuda.OutOfMemoryError as exc:
            torch.cuda.empty_cache()
            raise PipelineError("MODEL_OOM", "F5-TTS reference encode OOM") from exc
        return {"model_path": str(out_model), "model_version": F5_VERSION}

    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        import cv2

        from app.pipelines.avatar_creation.ml.loaders import get_face_analyzer

        app = get_face_analyzer()
        best, best_score, pose_samples = None, -1.0, []
        multi = 0
        for fp in sorted(frame_dir.glob("*.jpg")):
            img = cv2.imread(str(fp))
            faces = app.get(img)
            if not faces:
                continue
            if len(faces) > 1:
                multi += 1
                faces = [
                    max(
                        faces,
                        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                    )
                ]
            f = faces[0]
            pose_samples.append(list(f.pose))
            score = float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
            if score > best_score:
                best, best_score = (img, f), score
        if best is None:
            raise PipelineError("NO_FACE_DETECTED", "no face found in sampled frames")
        img, face = best
        x1, y1, x2, y2 = (int(v) for v in face.bbox)
        pad = int(0.35 * (y2 - y1))
        crop = img[max(0, y1 - pad) : y2 + pad, max(0, x1 - pad) : x2 + pad]
        cv2.imwrite(str(out_face), cv2.resize(crop, (512, 512)))
        cv2.imwrite(str(out_thumb), cv2.resize(crop, (256, 256)))
        return {
            "bbox": [x1, y1, x2, y2],
            "crop_size": [512, 512],
            "quality_score": min(best_score / 500.0, 1.0),
            "pose_samples": pose_samples,
        }

    def prep_appearance(
        self, face: Path, out_template: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        from app.pipelines.avatar_creation.ml.loaders import get_liveportrait

        lp = get_liveportrait()
        template = lp.prepare_source(str(face))
        import pickle as _pickle

        with out_template.open("wb") as fh:
            _pickle.dump(template, fh)
        return {"path": str(out_template), "model": LIVEPORTRAIT_VERSION}
