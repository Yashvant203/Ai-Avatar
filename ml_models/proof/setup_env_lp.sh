#!/usr/bin/env bash
# envLP: LivePortrait (torch 2.3.0/cu121), isolated env.
# Usage: bash setup_env_lp.sh [ROOT]   (ROOT defaults to /tmp/aiavatar)
set -euo pipefail

ENV=envLP
ROOT="${1:-/tmp/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[envLP] creating env (python 3.10)…"
[ -d "$ROOT/mamba/envs/$ENV" ] || "$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[envLP] installing torch 2.3.0 / cu121…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[envLP] cloning + installing LivePortrait…"
[ -d "$ROOT/LivePortrait" ] || git clone https://github.com/KwaiVGI/LivePortrait "$ROOT/LivePortrait"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r "$ROOT/LivePortrait/requirements.txt"

echo "[envLP] pinning torch back to 2.3.0/cu121 (in case requirements bumped it)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --force-reinstall --no-deps \
  torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[envLP] downloading LivePortrait weights…"
"$MAMBA" run -n "$ENV" huggingface-cli download KwaiVGI/LivePortrait \
  --local-dir "$ROOT/LivePortrait/pretrained_weights" \
  --exclude "*.git*" "README.md" "docs"

echo "[envLP] verifying torch…"
"$MAMBA" run -n "$ENV" python -c "import torch, torchvision; print('torch', torch.__version__, 'tv', torchvision.__version__, 'cuda', torch.cuda.is_available())"

echo "[envLP] READY"
