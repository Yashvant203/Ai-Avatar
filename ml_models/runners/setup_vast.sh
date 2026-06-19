#!/usr/bin/env bash
# One-shot bring-up for a rented GPU box (Vast.ai / RunPod / Lambda) on a CUDA
# 12.1-compatible GPU (Ampere/Ada/Hopper — A100, RTX 3090/4090, H100). NOT for
# Blackwell (RTX 5090 / B200): those need a torch 2.7/cu128 env upgrade first.
#
# Builds envF5 + envEM, installs the backend, launches worker + API (full-quality
# EchoMimic settings), and opens a public cloudflared URL for the website.
#
# Usage (from the cloned repo):
#   bash ml_models/runners/setup_vast.sh            # ROOT defaults to /workspace/aiavatar
#   bash ml_models/runners/setup_vast.sh /data/ai   # custom persistent ROOT
#
# Persistent disk: keep ROOT on the instance's persistent volume (Vast: /workspace)
# so the 13 GB weights download ONCE and survive reboots.
set -euo pipefail

ROOT="${1:-/workspace/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNNERS="$REPO/ml_models/runners"
BACKEND="$REPO/backend"
STORAGE="$ROOT/storage"
mkdir -p "$ROOT" "$STORAGE"

echo "==> repo:    $REPO"
echo "==> root:    $ROOT (envs + weights live here)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || {
  echo "!! no GPU visible (nvidia-smi failed) — wrong instance?"; exit 1; }

# 1. Build the two micromamba envs (idempotent; reuses cached weights if present).
echo "==> [1/4] building envF5 (voice)…"
bash "$RUNNERS/setup_env_f5.sh" "$ROOT"
echo "==> [2/4] building envEM (EchoMimic + weights)…"
bash "$RUNNERS/setup_env_em.sh" "$ROOT"

# 2. Install + migrate the FastAPI backend in the box's base python.
echo "==> [3/4] installing backend…"
pip install -e "$BACKEND"
( cd "$BACKEND" && alembic upgrade head )

# 3. Launch worker + API (full-quality echomimic — the GPU can take it). nohup so
#    they survive SSH disconnects; start in their own session so a stray Ctrl-C
#    in the shell can't kill them.
echo "==> [4/4] launching worker + API…"
export PIPELINE_BACKEND=real GENERATION_ENGINE=echomimic USE_INSIGHTFACE=false
export STORAGE_DIR="$STORAGE" AI_ROOT="$ROOT" CORS_ORIGINS='*'
export ECHOMIMIC_STEPS="${ECHOMIMIC_STEPS:-20}" OUTPUT_FPS="${OUTPUT_FPS:-25}"
export JWT_SECRET="${JWT_SECRET:-$(python -c 'import secrets;print(secrets.token_urlsafe(48))')}"
pkill -f 'worker.main' 2>/dev/null || true
pkill -f 'uvicorn app.main' 2>/dev/null || true
( cd "$BACKEND" && setsid nohup python -m worker.main \
    > "$ROOT/worker.log" 2>&1 & )
( cd "$BACKEND" && setsid nohup uvicorn app.main:app --host 0.0.0.0 --port 7860 \
    > "$ROOT/api.log" 2>&1 & )
sleep 8
if curl -fsS http://127.0.0.1:7860/healthcheck >/dev/null 2>&1; then
  echo "==> API healthy on :7860"
else
  echo "!! API not healthy — last api.log lines:"; tail -n 30 "$ROOT/api.log"; exit 1
fi

# 4. Public URL via cloudflared (works without opening instance ports).
if [ ! -x /usr/local/bin/cloudflared ]; then
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
fi
pkill -f 'cloudflared tunnel' 2>/dev/null || true
setsid nohup cloudflared tunnel --no-autoupdate --url http://localhost:7860 \
  > "$ROOT/tunnel.log" 2>&1 &
URL=""
for _ in $(seq 1 30); do
  sleep 2
  URL="$(grep -o 'https://[-a-z0-9]*\.trycloudflare\.com' "$ROOT/tunnel.log" | head -1 || true)"
  [ -n "$URL" ] && break
done

echo
echo "============================================================"
echo " READY. Public API URL:"
echo "   ${URL:-NOT FOUND — check $ROOT/tunnel.log}"
echo
echo " Put it in frontend/.env.local:"
echo "   NEXT_PUBLIC_API_BASE_URL=${URL:-<url>}"
echo " then: cd frontend && npm run dev"
echo
echo " Logs:   $ROOT/{worker,api,tunnel}.log"
echo " Speed:  ECHOMIMIC_STEPS=$ECHOMIMIC_STEPS OUTPUT_FPS=$OUTPUT_FPS"
echo "         (re-run with ECHOMIMIC_STEPS=8 OUTPUT_FPS=12 for fast previews)"
echo "============================================================"
