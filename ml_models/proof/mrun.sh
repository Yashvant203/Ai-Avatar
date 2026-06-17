#!/usr/bin/env bash
# Run a command inside a proof micromamba env.
# Usage: bash mrun.sh ENVNAME cmd [args...]
#   e.g. bash mrun.sh envA python script.py
# Honors PROOF_ROOT (defaults to /kaggle/working) for the micromamba install + envs.
set -euo pipefail

ROOT="${PROOF_ROOT:-/kaggle/working}"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
exec "$ROOT/bin/micromamba" run -n "$1" "${@:2}"
