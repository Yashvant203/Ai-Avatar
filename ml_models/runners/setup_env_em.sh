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

# OpenAI CLIP (a requirements.txt entry) has a legacy setup.py that breaks under
# the newest setuptools pip uses in its ISOLATED build env. Pin build tooling and
# install CLIP first with --no-build-isolation so it uses the env's setuptools;
# the matching spec then registers as "already satisfied" in requirements.txt.
echo "[envEM] pinning build tooling (CLIP's legacy setup.py needs older setuptools)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -U "setuptools<81" wheel
echo "[envEM] installing OpenAI CLIP (no build isolation)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --no-build-isolation \
  "clip @ https://github.com/openai/CLIP/archive/d50d76daa670286dd6cacf3bcd80b5e4823fc8e1.zip#sha256=b5842c25da441d6c581b53a5c60e0c2127ebafe0f746f8e15561a006c6c3be6a"

echo "[envEM] installing EchoMimic requirements (CLIP already installed; filtered out)…"
# pip re-fetches+rebuilds direct-URL reqs even when installed, so the clip @ url line
# would fail again under build isolation. Drop it from the list; clip is already in.
REQ_NOCLIP="/tmp/echomimic_req_noclip.txt"
grep -ivE '^[[:space:]]*clip[[:space:]]*@' "$REPO/requirements.txt" > "$REQ_NOCLIP"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r "$REQ_NOCLIP"
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
