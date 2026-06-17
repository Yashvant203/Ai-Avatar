#!/usr/bin/env bash
# Container entrypoint: migrate, launch the generation worker in the background,
# then run the API (which also serves the SPA) in the foreground.
set -euo pipefail

cd /app/backend

PORT="${PORT:-7860}"

echo "[start] applying migrations…"
alembic upgrade head

echo "[start] launching generation worker…"
python -m worker.main &
WORKER_PID=$!

# Forward shutdown signals to the worker.
trap 'echo "[start] stopping…"; kill "$WORKER_PID" 2>/dev/null || true; exit 0' SIGTERM SIGINT

echo "[start] launching API on :${PORT}…"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
