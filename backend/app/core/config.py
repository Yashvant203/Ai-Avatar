"""Application settings, loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Placeholder secret shipped in .env.example — must never be used in production.
_DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    """Typed application configuration.

    Values come from environment variables or a local `.env` file (see
    `.env.example`). See SYSTEM_ARCHITECTURE.md for the canonical list.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./ai_avatar.db"

    # Filesystem
    STORAGE_DIR: Path = Path("../storage")
    ML_MODELS_DIR: Path = Path("../ml_models")

    # Deployment: when set to a built Next.js static export dir, FastAPI serves
    # the SPA same-origin (single-container demo). Unset in local dev.
    FRONTEND_DIST: Path | None = None

    # Avatar creation — upload constraints + pipeline backend
    MAX_UPLOAD_MB: int = 500
    ALLOWED_VIDEO_TYPES: Annotated[list[str], NoDecode] = [
        "video/mp4",
        "video/quicktime",
        "video/webm",
    ]
    MIN_VIDEO_SECONDS: float = 10.0  # short self-recorded clips are fine (driving-based)
    MAX_VIDEO_SECONDS: float = 600.0  # 10 min
    # Pipeline ML backend: "auto" uses the real models if importable, else a
    # deterministic stub (ffmpeg + stdlib) so the pipeline runs without a GPU.
    PIPELINE_BACKEND: str = "auto"  # auto | real | stub

    # --- Real ML pipeline (subprocess runners) ---
    AI_ROOT: str = "/tmp/aiavatar"  # micromamba envs + model repos live here
    RUNNERS_DIR: str = "../ml_models/runners"  # relative to backend/ cwd
    MUSETALK_BBOX_SHIFT: int = 0  # tune per-face; range hint -20..18
    # Each avatar's motion comes from its OWN uploaded video: at creation we cut a
    # frontal, stable window of this length as the avatar's driving clip, then loop
    # it (palindrome) to the speech length at generation time.
    DRIVING_SECONDS: float = 6.0
    # Optional global fallback driving clip if an avatar has no driving.mp4 (unset
    # by default — the per-avatar clip is the real source of motion).
    IDLE_MOTION_PATH: str = "../ml_models/assets/idle_motion.mp4"
    ENV_F5: str = "envF5"
    ENV_LP: str = "envLP"
    ENV_MT: str = "envMT"
    ENV_EM: str = "envEM"
    # When False, avatar creation selects the face/half-body frame + driving clip
    # with ffmpeg only (no insightface), so the heavy envLP env can be skipped on
    # small-disk hosts (e.g. the EchoMimic-only setup on free Kaggle). Likeness then
    # depends on a clean, frontal upload rather than detector-picked framing.
    USE_INSIGHTFACE: bool = True

    # --- EchoMimic v2 (alternative generation engine, half-body + hand gestures) ---
    # Which visual engine the generation orchestrator uses:
    #   "liveportrait" → LivePortrait head motion + MuseTalk lip-sync (default)
    #   "echomimic"    → EchoMimic v2 single diffusion pass (gestures + lip-sync)
    GENERATION_ENGINE: str = "liveportrait"  # liveportrait | echomimic
    # EchoMimic v2 ships bundled pose templates under its repo's
    # assets/halfbody_demo/pose/<NAME>; "01" is the default demo gesture sequence.
    ECHOMIMIC_POSE_NAME: str = "01"
    # Conservative T4 defaults: EchoMimic v2 is a heavy diffusion model. Smaller
    # frame size + fewer steps reduce VRAM/time; raise on bigger GPUs.
    ECHOMIMIC_WIDTH: int = 768
    ECHOMIMIC_HEIGHT: int = 768
    ECHOMIMIC_STEPS: int = 20
    ECHOMIMIC_CFG: float = 2.5

    # Video generation
    MAX_SCRIPT_CHARS: int = 5000
    WORDS_PER_SECOND: float = 2.5  # speaking rate for duration estimates
    OUTPUT_FPS: int = 25
    WORKER_POLL_SECONDS: float = 2.0
    JOB_HEARTBEAT_TIMEOUT: int = 300  # stale-job reaper threshold (seconds)

    # Auth / JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALG: str = "HS256"
    ACCESS_TTL: int = 900  # seconds
    REFRESH_TTL: int = 1_209_600  # seconds

    # CORS — comma-separated string in env, parsed to a list.
    # NoDecode prevents pydantic-settings from JSON-decoding the raw env value
    # before our validator runs (so "a,b" is accepted, not just '["a","b"]').
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", "ALLOWED_VIDEO_TYPES", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @model_validator(mode="after")
    def _enforce_strong_secret_in_prod(self) -> Settings:
        """Refuse to boot in production with the default/weak JWT secret.

        Catches the most common deploy mistake (shipping the example secret),
        which would let anyone forge valid tokens.
        """
        if self.is_production and (
            self.JWT_SECRET == _DEFAULT_JWT_SECRET or len(self.JWT_SECRET) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be set to a strong (>=32 char) value in production. "
                'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
