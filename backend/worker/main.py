"""Standalone generation worker.

Run as:  python -m worker.main   (from the backend/ directory)

A long-lived loop that reaps zombie jobs, claims the oldest queued job, and runs
the generation orchestrator. Concurrency is 1 (single GPU). Exceptions are caught
so the loop never dies (VIDEO_GENERATION_PIPELINE.md §7).
"""

from __future__ import annotations

import signal
import time
import traceback

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.pipelines.generation.ml.loaders import get_generation_backend
from app.pipelines.generation.orchestrator import run_generation_job
from app.queue import db_queue

logger = get_logger("worker")

_running = True


def _handle_signal(signum, _frame) -> None:  # pragma: no cover - signal path
    global _running
    logger.info("worker received signal %s, shutting down after current job", signum)
    _running = False


def run_once() -> bool:
    """Reap zombies and process at most one job. Returns True if a job ran."""
    db = SessionLocal()
    try:
        db_queue.requeue_zombie_jobs(db)
        job = db_queue.claim_next_job(db)
        if job is None:
            return False
        logger.info("claimed job %s (avatar=%s)", job.id, job.avatar_id)
        try:
            run_generation_job(db, job)
        except Exception:  # noqa: BLE001
            traceback.print_exc()  # already recorded as failed in the DB
        return True
    finally:
        db.close()


def worker_main() -> None:  # pragma: no cover - long-running loop
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    # Warm the model cache once (no-op for the stub backend).
    get_generation_backend()
    logger.info("worker started (poll=%.1fs)", settings.WORKER_POLL_SECONDS)
    while _running:
        try:
            did_work = run_once()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            did_work = False
        if not did_work:
            time.sleep(settings.WORKER_POLL_SECONDS)
    logger.info("worker stopped")


if __name__ == "__main__":  # pragma: no cover
    worker_main()
