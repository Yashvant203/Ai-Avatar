# Free / low-cost GPU options + how to run the whole site

This platform needs a **CUDA GPU (~8–16 GB VRAM)** to run the real models
(F5-TTS voice clone, LivePortrait animation, MuseTalk lip-sync). The API, the
worker, and the Next.js UI are all CPU-light; only the **generation worker**
needs the GPU. Everything else (signup, dashboards, queueing, download) runs
fine on CPU.

> If you only want to **demo the UX** (no real cloned voice/face), you don't need
> a GPU at all — run with `PIPELINE_BACKEND=stub` (the default falls back to it
> when no GPU is present) and it produces real placeholder MP4s. See Pattern C.

---

## TL;DR comparison

| Provider | Free GPU | VRAM | Session limit | Persistence | Best for |
|---|---|---|---|---|---|
| **Kaggle Notebooks** | T4 ×2 / P100 | 16 GB | 9 h/run, ~30 h/wk | Kaggle **Datasets** (weights) | **Recommended** dev + batch runs |
| **Google Colab (free)** | T4 (sometimes) | ~15 GB | ~12 h, idle-disconnect | Google Drive mount | Quick experiments |
| **HF Spaces — ZeroGPU** | A100 (shared, queued) | 40 GB slice | per-call seconds–minutes | ephemeral | Hosting inference behind the UI |
| **Lightning AI Studio** | T4 / A10G | 16–24 GB | ~22 GPU-h/mo free | **persistent** studio | Always-ready dev env |
| **Modal** | serverless T4/A10G/A100 | 16–40 GB | per-call, $30/mo credits | volumes | **Production worker** (autoscaling) |
| **Paperspace Gradient (free)** | M4000 / Free-GPU | 8 GB | 6 h, availability-gated | persistent (paid) | Occasional runs |

Cheap-but-not-free (when you outgrow free): **RunPod**, **Vast.ai**, **Modal paid**,
**Lambda** — $0.2–0.6/hr for a decent GPU.

---

## The three ways to run the site

```
Pattern A — All-in-one on a GPU notebook (simplest, ephemeral)
  [Kaggle/Colab GPU session]
     uvicorn (API+UI)  +  worker  +  SQLite + local storage
              │
        cloudflared/ngrok tunnel  ──►  public https URL  = your website

Pattern B — Split (always-on UI, GPU worker on demand)
  [HF Space / Render / Railway — CPU, always on]  UI + API
              │  shared Postgres (Neon/Supabase) + shared object storage (S3/R2)
  [Modal / Kaggle — GPU]  worker pulls jobs from the shared queue

Pattern C — Demo only (no GPU)
  [HF Space free CPU]  UI + API + worker with PIPELINE_BACKEND=stub
```

- **Pattern A** is the fastest path to "my whole website on a free GPU". One
  session runs everything; a tunnel gives you a public URL. Downside: it dies
  when the session ends (9 h on Kaggle) and storage is wiped.
- **Pattern B** is the real architecture: keep the UI/API always-on on a free
  CPU host, run the GPU worker elsewhere. Requires moving SQLite → Postgres and
  local storage → object storage (both have generous free tiers). This is the
  recommended production shape; the code's queue is already DB-backed.
- **Pattern C** is what the included `Dockerfile` ships by default (HF Space).

---

## 1) Kaggle Notebooks — recommended

Free 16 GB T4×2, the project's primary dev target. Weights persist in a Kaggle
**Dataset** so you don't re-download every session.

```python
# In a Kaggle notebook cell (Settings → Accelerator: GPU T4 x2, Internet: ON)
!git clone https://github.com/<you>/ai-avatar-platform.git
%cd ai-avatar-platform/backend
!pip install -e . -q
!python ../ml_models/setup_ffmpeg.sh || apt-get -y install ffmpeg
!python ../ml_models/download_models.py        # → ml_models/weights/
!python ../ml_models/verify_env.py             # asserts GPU + ffmpeg + weights

# Run the full stack + expose it publicly with a Cloudflare quick tunnel:
!alembic upgrade head
import subprocess, os
os.environ["JWT_SECRET"] = "use-a-long-random-value"
subprocess.Popen(["python", "-m", "worker.main"])
subprocess.Popen(["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"])
# Quick tunnel (no account):
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared
!./cloudflared tunnel --url http://localhost:7860   # prints a public https URL
```

See `ml_models/kaggle_runner.ipynb` for a ready notebook (clone → download →
verify → end-to-end create+generate → cache weights to a Dataset).

**Limits:** 9 h/session, ~30 GPU-h/week, no always-on server. Use it for dev,
batch generation, and weight caching — not 24/7 hosting.

## 2) Google Colab (free)

```python
# Runtime → Change runtime type → T4 GPU
!git clone https://github.com/<you>/ai-avatar-platform.git
%cd ai-avatar-platform/backend
!pip install -e . -q && apt-get -y install ffmpeg
!python ../ml_models/download_models.py
!alembic upgrade head
# Expose with ngrok (needs a free authtoken) or cloudflared (no account):
!pip install pyngrok -q
from pyngrok import ngrok; ngrok.set_auth_token("<token>")
import subprocess; subprocess.Popen(["python","-m","worker.main"])
subprocess.Popen(["uvicorn","app.main:app","--port","7860"])
print(ngrok.connect(7860).public_url)   # your website URL
```

**Limits:** GPU availability is not guaranteed on free; idle/12 h disconnects;
mount Google Drive to persist weights (`from google.colab import drive`).

## 3) Hugging Face Spaces — ZeroGPU (free A100 slices)

Free CPU Spaces can't run the models, but **ZeroGPU** (free with an HF account,
shared A100, queued) lets specific functions grab a GPU per-call via the
`spaces.GPU` decorator. Pattern: deploy the UI/API on the Space (CPU) and wrap
the generation stages so they request a GPU slice. Good for a hosted, public
demo with *real* generation at low/no cost, accepting queue latency.

- Deploy: this repo's `Dockerfile` + `README_HF.md` (see `hf_spaces.md`).
- For ZeroGPU you typically use the **Gradio/Python SDK** wrapper around the
  inference functions rather than a long-running worker; document as a follow-up.

## 4) Lightning AI Studio

Free monthly GPU credits (~22 h, T4/A10G) with a **persistent** environment that
keeps your weights and DB between sessions — closest to "always there" on the
free tier.

```bash
# In a Lightning Studio terminal (switch the machine to a GPU)
git clone https://github.com/<you>/ai-avatar-platform.git && cd ai-avatar-platform/backend
pip install -e . && sudo apt-get install -y ffmpeg
python ../ml_models/download_models.py
alembic upgrade head
python -m worker.main &           # GPU worker
uvicorn app.main:app --host 0.0.0.0 --port 7860
# Use the Studio's built-in port-forwarding/share to get a public URL.
```

## 5) Modal — serverless GPU (best for the worker)

$30/month free credits, true serverless GPUs (T4/A10G/A100). Ideal for **Pattern
B**: host UI+API on a free CPU host, run the worker on Modal so it scales to zero
when idle (you only spend credits while generating).

```python
# modal_worker.py (sketch)
import modal
image = (modal.Image.debian_slim().apt_install("ffmpeg")
         .pip_install_from_pyproject("backend/pyproject.toml"))
app = modal.App("ai-avatar-worker", image=image)

@app.function(gpu="a10g", timeout=1800, volumes={"/weights": modal.Volume.from_name("aa-weights")})
def run_pending_jobs():
    # point DATABASE_URL at shared Postgres, STORAGE_DIR at a shared volume / S3
    from worker.main import run_once
    while run_once():
        pass
```

Schedule `run_pending_jobs` on a cron (e.g. every minute) or trigger it from the
API after enqueue. Requires shared DB + storage (next section).

---

## Making it your real always-on website (Pattern B specifics)

Free local SQLite + local files only work in a single process/host. To split UI
from GPU, swap two things — both have free tiers and the code is mostly ready:

1. **Database → Postgres.** Set `DATABASE_URL=postgresql+psycopg://…` (Neon,
   Supabase, or Railway free Postgres). SQLAlchemy/Alembic already support it;
   drop the SQLite-only PRAGMA path (guarded by `_is_sqlite` already) and run
   `alembic upgrade head` against Postgres.
2. **Storage → object storage.** Put uploads/avatars/voices/outputs in S3-
   compatible storage (Cloudflare R2 / Backblaze B2 / AWS S3 free tier) and have
   `core/paths.py` + the download endpoint stream from there. (Local FS is the
   current implementation — this is the one real code change Pattern B needs.)

Then: UI+API on a free always-on host (HF Space CPU, Render, Railway, Fly.io),
GPU worker on Modal/Kaggle pulling from the shared queue. The DB-backed queue we
built (`app/queue/db_queue.py`, atomic claim + zombie reaper) works unchanged
across hosts once the DB is shared.

---

## Quick decision guide

- **"I just want to show the website working"** → Pattern C (HF Space, free CPU,
  stub backend). Zero GPU, instant.
- **"I want real generation, cheaply, now"** → Pattern A on **Kaggle** + a
  cloudflared tunnel. Free 16 GB GPU, public URL in minutes (ephemeral).
- **"I want a real always-on product"** → Pattern B: free CPU host for UI/API +
  **Modal** GPU worker + Neon Postgres + Cloudflare R2.
