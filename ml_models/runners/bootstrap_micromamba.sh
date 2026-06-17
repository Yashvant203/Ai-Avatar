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

_works() { [ -x "$ROOT/bin/micromamba" ] && "$ROOT/bin/micromamba" --version >/dev/null 2>&1; }

if ! _works; then
  echo "[mamba] downloading micromamba…"
  mkdir -p "$ROOT/bin"
  rm -f "$ROOT/bin/micromamba"
  # Method 1: direct static binary from GitHub releases (no fragile curl|tar pipe).
  curl -L --fail --retry 5 --retry-delay 3 -o "$ROOT/bin/micromamba" \
    https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64 \
    && chmod +x "$ROOT/bin/micromamba" || true
  # Method 2: fallback to the micro.mamba.pm tarball, to a FILE then extract (not piped).
  if ! _works; then
    echo "[mamba] direct binary failed; falling back to micro.mamba.pm tarball…"
    rm -f "$ROOT/bin/micromamba" "$ROOT/mm.tar.bz2"
    curl -L --fail --retry 5 --retry-delay 3 -o "$ROOT/mm.tar.bz2" \
      https://micro.mamba.pm/api/micromamba/linux-64/latest
    tar -xjf "$ROOT/mm.tar.bz2" -C "$ROOT" bin/micromamba
    chmod +x "$ROOT/bin/micromamba"
    rm -f "$ROOT/mm.tar.bz2"
  fi
fi

if ! _works; then
  echo "[mamba] ERROR: micromamba install failed (network?). Re-run this cell." >&2
  exit 1
fi
"$ROOT/bin/micromamba" --version
echo "[mamba] ready at $ROOT/bin/micromamba"
