#!/usr/bin/env bash
# Install a standalone micromamba (conda replacement) under ROOT/bin.
# Kaggle images don't reliably expose `conda`, so we bring our own — a single
# static binary, no base install needed. Idempotent.
# Usage: bash bootstrap_micromamba.sh [ROOT]   (ROOT defaults to /kaggle/working)
set -euo pipefail

ROOT="${1:-/kaggle/working}"
cd "$ROOT"

if [ ! -x "$ROOT/bin/micromamba" ]; then
  echo "[mamba] downloading micromamba…"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba
fi

"$ROOT/bin/micromamba" --version
echo "[mamba] ready at $ROOT/bin/micromamba"
