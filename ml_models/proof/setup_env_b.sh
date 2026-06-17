#!/usr/bin/env bash
# env-B: Python 3.10, torch 2.0.1/cu118 — MuseTalk v1.5 + mmcv stack.
# Usage: bash setup_env_b.sh [ROOT]   (ROOT defaults to /kaggle/working)
# NOTE: mmcv is the highest-risk step. Order is non-negotiable: torch FIRST, then mim.
set -euo pipefail

ENV=envB
ROOT="${1:-/kaggle/working}"
cd "$ROOT"

echo "[env-B] creating conda env (python 3.10)…"
conda create -y -n "$ENV" python=3.10

echo "[env-B] installing torch 2.0.1 / cu118 (must precede mmcv)…"
conda run -n "$ENV" pip install --no-cache-dir \
  torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118

echo "[env-B] cloning + installing MuseTalk requirements…"
[ -d MuseTalk ] || git clone https://github.com/TMElyralab/MuseTalk
conda run -n "$ENV" pip install --no-cache-dir -r MuseTalk/requirements.txt

echo "[env-B] installing MMLab stack via mim (mmengine → mmcv → mmdet → mmpose)…"
conda run -n "$ENV" pip install --no-cache-dir -U openmim
conda run -n "$ENV" mim install mmengine
conda run -n "$ENV" mim install "mmcv==2.0.1"
conda run -n "$ENV" mim install "mmdet==3.1.0"
conda run -n "$ENV" mim install "mmpose==1.1.0"

echo "[env-B] downloading MuseTalk weights (force public HF endpoint)…"
cd "$ROOT/MuseTalk"
# download_weights.sh hardcodes the China mirror; switch it to the public endpoint.
sed -i 's#https://hf-mirror.com#https://huggingface.co#g' download_weights.sh || true
conda run -n "$ENV" bash download_weights.sh

echo "[env-B] verifying mmcv + musetalk weights…"
conda run -n "$ENV" python -c "import torch, mmcv; print('torch', torch.__version__, 'mmcv', mmcv.__version__)"
test -f "$ROOT/MuseTalk/models/musetalkV15/unet.pth" && echo "musetalk v15 weights OK"

echo "[env-B] READY"
