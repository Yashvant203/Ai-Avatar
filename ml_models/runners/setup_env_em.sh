#!/usr/bin/env bash
# envEM: EchoMimic v2 (torch 2.5.1/cu121 + xformers), isolated env.
# Usage: bash setup_env_em.sh [ROOT]   (ROOT defaults to /tmp/aiavatar)
set -euo pipefail

ENV=envEM
ROOT="${1:-/tmp/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
export MPLBACKEND=Agg
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[envEM] creating env (python 3.10)…"
[ -d "$ROOT/mamba/envs/$ENV" ] || "$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[envEM] cloning EchoMimic v2…"
REPO="$ROOT/EchoMimicV2"
[ -d "$REPO" ] || git clone https://github.com/antgroup/echomimic_v2 "$REPO"

echo "[envEM] installing torch 2.5.1 / cu121 + xformers…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121
"$MAMBA" run -n "$ENV" pip install --no-cache-dir xformers==0.0.28.post3 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[envEM] installing EchoMimic requirements…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r "$REPO/requirements.txt"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --no-deps facenet_pytorch==2.6.0

echo "[envEM] pinning torch + xformers back (in case requirements bumped them)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --force-reinstall --no-deps \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --force-reinstall --no-deps \
  xformers==0.0.28.post3 \
  --index-url https://download.pytorch.org/whl/cu121

# Weights: cached dataset (WEIGHTS_SRC/em_weights) if provided, else download.
WTS="$REPO/pretrained_weights"
if [ -n "${WEIGHTS_SRC:-}" ] && [ -d "$WEIGHTS_SRC/em_weights" ]; then
  echo "[envEM] restoring EchoMimic weights from cache: $WEIGHTS_SRC/em_weights"
  mkdir -p "$WTS"
  cp -rn "$WEIGHTS_SRC/em_weights/." "$WTS/"
else
  echo "[envEM] downloading EchoMimic v2 weights (BadToBest/EchoMimicV2)…"
  "$MAMBA" run -n "$ENV" huggingface-cli download BadToBest/EchoMimicV2 \
    --local-dir "$WTS" --exclude "*.git*" "README.md"
fi

# Some infer.yaml paths reference external base models; fetch only if missing.
[ -d "$WTS/sd-image-variations-diffusers" ] || \
  "$MAMBA" run -n "$ENV" huggingface-cli download lambdalabs/sd-image-variations-diffusers \
    --local-dir "$WTS/sd-image-variations-diffusers" --exclude "*.git*" || true
[ -d "$WTS/wav2vec2-base-960h" ] || \
  "$MAMBA" run -n "$ENV" huggingface-cli download facebook/wav2vec2-base-960h \
    --local-dir "$WTS/wav2vec2-base-960h" --exclude "*.git*" || true

echo "[envEM] verifying torch + key weights…"
"$MAMBA" run -n "$ENV" python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
for f in denoising_unet.pth reference_unet.pth motion_module.pth pose_encoder.pth; do
  [ -f "$WTS/$f" ] && echo "[envEM] ok: $f" || echo "[envEM] WARN missing: $WTS/$f"
done

echo "[envEM] READY"
