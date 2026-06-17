#!/usr/bin/env bash
# Snapshot the BUILT micromamba envs + model repos + caches into one tarball, so a
# future Kaggle session can restore them and skip the ~25-min rebuild.
# Excludes storage/ (user avatars/outputs) — that's not part of the environment.
#
# Usage: bash snapshot_envs.sh [ROOT] [OUT]
#   ROOT defaults to /tmp/aiavatar, OUT to /kaggle/working/aiavatar_envs.tgz
# After it finishes: Output panel -> aiavatar_envs.tgz -> "New Dataset" (ai-avatar-envs).
set -euo pipefail

ROOT="${1:-/tmp/aiavatar}"
OUT="${2:-/kaggle/working/aiavatar_envs.tgz}"

# Quiesce the servers so files aren't changing mid-tar (ignore if not running).
pkill -f worker.main 2>/dev/null || true
pkill -f "uvicorn app.main" 2>/dev/null || true

echo "[snapshot] taring envs + repos + caches -> $OUT (a few minutes)…"
tar -C / -czf "$OUT" \
  --exclude="${ROOT#/}/storage" \
  "${ROOT#/}" \
  root/.cache/huggingface \
  root/.insightface 2>/dev/null || true

echo "[snapshot] done: $(du -h "$OUT" | cut -f1) -> $OUT"
echo "[snapshot] Next: Output panel -> $OUT -> New Dataset (name it 'ai-avatar-envs')."
