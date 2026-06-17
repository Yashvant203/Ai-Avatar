"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    """Configure root logging once. JSON-ish single-line records in production,
    human-readable in development."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = logging.INFO if settings.is_production else logging.DEBUG

    if settings.is_production:
        fmt = (
            '{"ts":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","msg":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Tame noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
