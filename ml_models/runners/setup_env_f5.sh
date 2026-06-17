#!/usr/bin/env bash
# envF5: F5-TTS voice cloning, isolated env.
# Plain FULL install (no --no-deps) — f5-tts pulls a CUDA torch + all its deps
# (hydra, unidecode, torchcodec, …). Isolation means it can't clash with LivePortrait.
# Usage: bash setup_env_f5.sh [ROOT]   (ROOT defaults to /tmp/aiavatar)
set -euo pipefail

ENV=envF5
ROOT="${1:-/tmp/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
export MPLBACKEND=Agg  # Kaggle's inline matplotlib backend is invalid in these envs

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[envF5] creating env (python 3.10)…"
[ -d "$ROOT/mamba/envs/$ENV" ] || "$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[envF5] installing f5-tts (full deps)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir f5-tts

echo "[envF5] verifying…"
"$MAMBA" run -n "$ENV" python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); from f5_tts.api import F5TTS; print('f5_tts OK')"

echo "[envF5] READY"
