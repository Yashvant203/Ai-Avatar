"""Training-script generation.

Deterministic and fully local — NO commercial API. We assemble a phonetically
rich, expression-varied passage (~450–650 words) that exercises a broad phoneme
set and natural prosody, which improves both the F5-TTS voice reference and the
neutral-pose capture (AVATAR_CREATION_PIPELINE.md §3). The passage is selected
deterministically from a curated pool so re-requesting is stable per avatar.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.training_script import TrainingScript

# Curated, phoneme-dense paragraphs. Each targets different articulations
# (plosives, fricatives, nasals, diphthongs) and emotional cadence.
_PARAGRAPHS: list[str] = [
    (
        "Hello, my name is recorded here so this device can learn the music of my "
        "voice. I speak clearly and calmly, letting each word breathe. The quick "
        "brown fox jumps over the lazy dog, while bright jackdaws vex my big sphinx "
        "of quartz."
    ),
    (
        "Numbers matter too: one, two, three, fourteen, fifty, ninety-nine, and a "
        "thousand and six. On June third, twenty twenty-six, we measured roughly "
        "3.5 metres of cable and paid twelve dollars for coffee."
    ),
    (
        "Now I will shift my tone. Isn't it wonderful how a question lifts at the "
        "end? And then a firm statement lands with weight. Stop. Breathe. Begin "
        "again, smoothly, with warmth and a gentle smile."
    ),
    (
        "Words with tricky sounds help the most: thorough, vision, beige garage, "
        "rural squirrel, sixth sense, judge, church, azure, and the thrilling "
        "thunderstorm rolling through the southern shore."
    ),
    (
        "I enjoy long, flowing sentences that wander like a river, gathering "
        "clauses and commas, pausing for thought, then arriving at a clear and "
        "confident conclusion that anyone listening can easily follow."
    ),
    (
        "Finally, a short burst of energy! Wow, fantastic, amazing — we did it. "
        "Thank you for listening. When you are ready, press stop, and your avatar "
        "will begin to take shape."
    ),
]

_INTRO = (
    "Please read this aloud at a natural pace, as if speaking to a friend. "
    "Look toward the camera and keep your head fairly still.\n\n"
)


def _word_count(text: str) -> int:
    return len(text.split())


def generate_script_text(avatar_id: int, language: str = "en") -> str:
    """Assemble a deterministic, phoneme-rich passage for the given avatar.

    Deterministic ordering keyed on avatar_id keeps repeat requests stable while
    giving different avatars a slightly different paragraph order.
    """
    n = len(_PARAGRAPHS)
    offset = avatar_id % n
    ordered = [_PARAGRAPHS[(offset + i) % n] for i in range(n)]
    return _INTRO + "\n\n".join(ordered)


def create_script_for_avatar(
    db: Session, *, user_id: int, avatar_id: int, language: str = "en"
) -> TrainingScript:
    """Generate and persist a training script for an avatar."""
    content = generate_script_text(avatar_id, language)
    script = TrainingScript(
        user_id=user_id,
        avatar_id=avatar_id,
        content=content,
        word_count=_word_count(content),
        language=language,
    )
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def get_latest_script(db: Session, *, avatar_id: int) -> TrainingScript | None:
    return (
        db.query(TrainingScript)
        .filter(TrainingScript.avatar_id == avatar_id)
        .order_by(TrainingScript.created_at.desc(), TrainingScript.id.desc())
        .first()
    )
