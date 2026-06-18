"""EchoMimic v2 config defaults."""

from __future__ import annotations

from app.core.config import Settings


def test_echomimic_defaults() -> None:
    s = Settings()
    assert s.GENERATION_ENGINE == "liveportrait"  # default stays the existing path
    assert s.ENV_EM == "envEM"
    assert s.ECHOMIMIC_POSE_NAME == "01"
    assert s.ECHOMIMIC_WIDTH == 768
    assert s.ECHOMIMIC_HEIGHT == 768
    assert s.ECHOMIMIC_STEPS == 20
    assert s.ECHOMIMIC_CFG == 2.5


def test_generation_engine_overridable(monkeypatch) -> None:
    monkeypatch.setenv("GENERATION_ENGINE", "echomimic")
    s = Settings()
    assert s.GENERATION_ENGINE == "echomimic"
