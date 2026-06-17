# Kaggle GPU dev workflow

Kaggle Notebooks (free T4×2 / P100, 16 GB) are the project's primary GPU dev
target — for **model-heavy runs** (avatar creation + video generation) and for
**caching model weights** to a Kaggle Dataset so they don't re-download.

## One-time setup

1. Create a Kaggle account; verify your phone to unlock GPU + internet.
2. New Notebook → **Settings**:
   - Accelerator: **GPU T4 x2** (or P100).
   - Internet: **On** (needed to pull weights from Hugging Face Hub).
3. (Optional) Add `HF_TOKEN` via **Add-ons → Secrets** if any model repo is gated.

## Run it

Use the ready notebook `ml_models/kaggle_runner.ipynb`, or paste:

```python
!git clone https://github.com/<you>/ai-avatar-platform.git
%cd ai-avatar-platform/backend
!pip install -e . -q
!apt-get -y install ffmpeg
!python ../ml_models/download_models.py          # → ml_models/weights/{f5_tts,musetalk,liveportrait}
!python ../ml_models/verify_env.py               # GPU + ffmpeg + weights present?
!alembic upgrade head
# run a real end-to-end pass (see notebook for the full create+generate flow)
```

## Cache weights to a Kaggle Dataset (avoid re-downloading)

1. After `download_models.py`, the weights are in `ml_models/weights/`.
2. **File → Add or upload data → New Dataset** from that folder (e.g.
   `ai-avatar-weights`).
3. In future notebooks, **Add Data → your dataset**; it mounts read-only at
   `/kaggle/input/ai-avatar-weights/`. Point `ML_MODELS_DIR` (or symlink
   `ml_models/weights`) at it and skip the download step.

## Limits to design around

- **9 hours** max per session; the kernel stops afterward.
- **~30 GPU-hours/week** quota.
- **No persistent server** — Kaggle is for batch/interactive runs, not 24/7
  hosting. To expose a temporary public URL during a session, use a cloudflared
  quick tunnel (see `free_gpu_options.md`, Pattern A).
- Storage under `/kaggle/working` is wiped when the session ends; commit the
  notebook to keep outputs, or push artifacts to a Dataset.

## When to use Kaggle vs. elsewhere

- **Kaggle:** development, debugging the real ML stages, batch generation,
  weight caching.
- **Always-on hosting:** not Kaggle — use HF Spaces (demo) or Pattern B
  (CPU host + Modal GPU worker). See `free_gpu_options.md`.
