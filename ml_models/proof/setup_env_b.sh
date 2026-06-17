#!/usr/bin/env bash
# env-B: Python 3.10, torch 2.0.1/cu118 — MuseTalk v1.5 + mmcv stack.
# Uses micromamba (no system conda needed). Usage: bash setup_env_b.sh [ROOT]
# NOTE: mmcv is the highest-risk step. Order is non-negotiable: torch FIRST, then mim.
set -euo pipefail

ENV=envB
ROOT="${1:-/kaggle/working}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[env-B] creating env (python 3.10)…"
"$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[env-B] installing torch 2.0.1 / cu118 (must precede mmcv)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118

echo "[env-B] cloning + installing MuseTalk requirements…"
[ -d MuseTalk ] || git clone https://github.com/TMElyralab/MuseTalk
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r MuseTalk/requirements.txt

echo "[env-B] installing MMLab stack via mim (mmengine → mmcv → mmdet → mmpose)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -U openmim
"$MAMBA" run -n "$ENV" mim install mmengine
"$MAMBA" run -n "$ENV" mim install "mmcv==2.0.1"
"$MAMBA" run -n "$ENV" mim install "mmdet==3.1.0"
"$MAMBA" run -n "$ENV" mim install "mmpose==1.1.0"

echo "[env-B] downloading MuseTalk weights (force public HF endpoint)…"
cd "$ROOT/MuseTalk"
# download_weights.sh hardcodes the China mirror; switch it to the public endpoint.
sed -i 's#https://hf-mirror.com#https://huggingface.co#g' download_weights.sh || true
"$MAMBA" run -n "$ENV" bash download_weights.sh

echo "[env-B] verifying mmcv + musetalk weights…"
"$MAMBA" run -n "$ENV" python -c "import torch, mmcv; print('torch', torch.__version__, 'mmcv', mmcv.__version__)"
test -f "$ROOT/MuseTalk/models/musetalkV15/unet.pth" && echo "musetalk v15 weights OK"

echo "[env-B] READY"
