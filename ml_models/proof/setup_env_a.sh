#!/usr/bin/env bash
# env-A: Python 3.10, torch 2.3.0/cu121 — F5-TTS + LivePortrait.
# Usage: bash setup_env_a.sh [ROOT]   (ROOT defaults to /kaggle/working)
set -euo pipefail

ENV=envA
ROOT="${1:-/kaggle/working}"
cd "$ROOT"

echo "[env-A] creating conda env (python 3.10)…"
conda create -y -n "$ENV" python=3.10

echo "[env-A] installing torch 2.3.0 / cu121…"
conda run -n "$ENV" pip install --no-cache-dir \
  torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[env-A] cloning + installing LivePortrait…"
[ -d LivePortrait ] || git clone https://github.com/KwaiVGI/LivePortrait
conda run -n "$ENV" pip install --no-cache-dir -r LivePortrait/requirements.txt

echo "[env-A] downloading LivePortrait weights…"
conda run -n "$ENV" huggingface-cli download KwaiVGI/LivePortrait \
  --local-dir LivePortrait/pretrained_weights \
  --exclude "*.git*" "README.md" "docs"

echo "[env-A] installing F5-TTS (no-deps to protect torch) + its deps…"
conda run -n "$ENV" pip install --no-cache-dir f5-tts --no-deps
conda run -n "$ENV" pip install --no-cache-dir \
  cached_path vocos x-transformers torchdiffeq ema-pytorch \
  jieba pypinyin transformers accelerate datasets pydub soundfile librosa tomli click

echo "[env-A] verifying imports…"
conda run -n "$ENV" python -c "import torch, f5_tts; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); from f5_tts.api import F5TTS; print('f5_tts OK')"

echo "[env-A] READY"
