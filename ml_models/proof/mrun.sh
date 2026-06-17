#!/usr/bin/env bash
# Run a command inside a proof micromamba env.
# Usage: bash mrun.sh ENVNAME cmd [args...]
#   e.g. bash mrun.sh envF5 python script.py
# Honors PROOF_ROOT (defaults to /tmp/aiavatar) for the micromamba install + envs.
set -euo pipefail

ROOT="${PROOF_ROOT:-/tmp/aiavatar}"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
exec "$ROOT/bin/micromamba" run -n "$1" "${@:2}"
