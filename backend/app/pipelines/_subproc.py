"""Run a command inside one of the Phase-0 micromamba envs via mrun.sh.

The FastAPI app/worker run in Kaggle's base env (no ML imports) and orchestrate
the real pipeline by shelling out to three isolated micromamba envs
(envF5/envLP/envMT) through the proven runner scripts. This is the single choke
point for that hand-off.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("pipeline.subproc")


def run_in_env(env: str, args: list[str], *, cwd: str | None = None) -> str:
    """Invoke `args` inside micromamba env `env` via mrun.sh.

    Returns captured stdout on success; raises RuntimeError (carrying the tail of
    stderr) on a non-zero exit so the orchestrators' generic handlers mark the
    job/avatar failed.
    """
    runners = Path(settings.RUNNERS_DIR).resolve()
    cmd = ["bash", str(runners / "mrun.sh"), env, *args]
    env_vars = {**os.environ, "PROOF_ROOT": settings.AI_ROOT}
    logger.info("run_in_env %s: %s", env, " ".join(args))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env_vars,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        logger.error("env %s failed (%s): %s", env, proc.returncode, proc.stderr[-2000:])
        raise RuntimeError(f"{env} runner failed: {proc.stderr[-500:]}")
    return proc.stdout
