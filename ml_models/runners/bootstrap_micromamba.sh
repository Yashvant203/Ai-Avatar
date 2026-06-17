#!/usr/bin/env bash
# Install a standalone micromamba (conda replacement) under ROOT/bin.
# Kaggle images don't reliably expose `conda`, so we bring our own — a single
# static binary, no base install needed. Idempotent.
# ROOT defaults to /tmp/aiavatar (big uncapped disk; /kaggle/working is capped ~20GB).
# Usage: bash bootstrap_micromamba.sh [ROOT]
set -euo pipefail

ROOT="${1:-/tmp/aiavatar}"
mkdir -p "$ROOT"
cd "$ROOT"

if [ ! -x "$ROOT/bin/micromamba" ]; then
  echo "[mamba] downloading micromamba…"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba
fi

"$ROOT/bin/micromamba" --version
echo "[mamba] ready at $ROOT/bin/micromamba"
