#!/usr/bin/env bash
# envMT: MuseTalk v1.5 (torch 2.0.1/cu118) + mmcv stack, isolated env.
# Usage: bash setup_env_mt.sh [ROOT]   (ROOT defaults to /tmp/aiavatar)
# NOTE: mmcv is the highest-risk step. Order is non-negotiable: torch FIRST, then mim.
set -euo pipefail

ENV=envMT
ROOT="${1:-/tmp/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
export MPLBACKEND=Agg  # Kaggle's inline matplotlib backend is invalid in these envs
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[envMT] creating env (python 3.10)…"
[ -d "$ROOT/mamba/envs/$ENV" ] || "$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[envMT] installing torch 2.0.1 / cu118 (must precede mmcv)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118

echo "[envMT] cloning + installing MuseTalk requirements…"
[ -d "$ROOT/MuseTalk" ] || git clone https://github.com/TMElyralab/MuseTalk "$ROOT/MuseTalk"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r "$ROOT/MuseTalk/requirements.txt"

echo "[envMT] installing MMLab stack via mim (mmengine → mmcv → mmdet → mmpose)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -U openmim
"$MAMBA" run -n "$ENV" mim install mmengine
"$MAMBA" run -n "$ENV" mim install "mmcv==2.0.1"
"$MAMBA" run -n "$ENV" mim install "mmdet==3.1.0"
"$MAMBA" run -n "$ENV" mim install "mmpose==1.1.0"

echo "[envMT] downloading MuseTalk weights (force public HF endpoint)…"
cd "$ROOT/MuseTalk"
sed -i 's#https://hf-mirror.com#https://huggingface.co#g' download_weights.sh || true
"$MAMBA" run -n "$ENV" bash download_weights.sh

echo "[envMT] verifying mmcv + musetalk weights…"
"$MAMBA" run -n "$ENV" python -c "import torch, mmcv; print('torch', torch.__version__, 'mmcv', mmcv.__version__)"
test -f "$ROOT/MuseTalk/models/musetalkV15/unet.pth" && echo "musetalk v15 weights OK"

echo "[envMT] READY"
