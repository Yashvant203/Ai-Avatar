#!/usr/bin/env bash
# env-A: Python 3.10, torch 2.3.0/cu121 — F5-TTS + LivePortrait.
# Uses micromamba (no system conda needed). Usage: bash setup_env_a.sh [ROOT]
set -euo pipefail

ENV=envA
ROOT="${1:-/kaggle/working}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[env-A] creating env (python 3.10)…"
"$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[env-A] installing torch 2.3.0 / cu121…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[env-A] cloning + installing LivePortrait…"
[ -d LivePortrait ] || git clone https://github.com/KwaiVGI/LivePortrait
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r LivePortrait/requirements.txt

echo "[env-A] downloading LivePortrait weights…"
"$MAMBA" run -n "$ENV" huggingface-cli download KwaiVGI/LivePortrait \
  --local-dir LivePortrait/pretrained_weights \
  --exclude "*.git*" "README.md" "docs"

echo "[env-A] installing F5-TTS (no-deps to protect torch) + its deps…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir f5-tts --no-deps
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  cached_path vocos x-transformers torchdiffeq ema-pytorch \
  jieba pypinyin transformers accelerate datasets pydub soundfile librosa tomli click

echo "[env-A] verifying imports…"
"$MAMBA" run -n "$ENV" python -c "import torch, f5_tts; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); from f5_tts.api import F5TTS; print('f5_tts OK')"

echo "[env-A] READY"
