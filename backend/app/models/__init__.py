"""ORM model registry.

Importing this package registers every model on `Base.metadata`. Alembic's
env.py does `import app.models`, and app startup imports models transitively,
so autogenerate and table creation see the full schema. Append new models here
as later phases add them.
"""

from app.models.avatar import Avatar  # noqa: F401
from app.models.generated_video import GeneratedVideo  # noqa: F401
from app.models.generation_job import GenerationJob  # noqa: F401
from app.models.training_script import TrainingScript  # noqa: F401
from app.models.training_video import TrainingVideo  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.voice_model import VoiceModel  # noqa: F401

__all__ = [
    "User",
    "Avatar",
    "TrainingScript",
    "TrainingVideo",
    "VoiceModel",
    "GenerationJob",
    "GeneratedVideo",
]
