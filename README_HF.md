---
title: AI Avatar Platform
emoji: 🗣️
colorFrom: yellow
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Self-hosted talking-head avatars (F5-TTS + LivePortrait + MuseTalk)
---

# AI Avatar Platform — Hugging Face Space

This Space runs the **combined demo container** (FastAPI API + static Next.js UI +
generation worker) defined in the repo `Dockerfile`. To deploy:

1. Create a new **Docker** Space.
2. Push this repository (or set the Space to build from the `Dockerfile`).
3. Add Space **Secrets** (Settings → Variables and secrets):
   - `JWT_SECRET` — a long random string (required in production).
   - `HF_TOKEN` — only if pulling gated model weights.
4. The Space boots on port **7860** via `scripts/start.sh`.

## ⚠️ Limitations (read `docs/deployment/hf_spaces.md`)

- **Free tier is CPU-only.** Real F5-TTS / LivePortrait / MuseTalk need a GPU.
  With `PIPELINE_BACKEND=auto` on CPU the app falls back to the **stub backend**,
  which produces a real (placeholder) MP4 so the *entire UX* is demoable — but it
  is not a real cloned-voice talking head. Use a **GPU Space** or an external GPU
  worker (see `docs/deployment/free_gpu_options.md`) for real generation.
- **Ephemeral storage.** The Space filesystem (incl. `storage/` and the SQLite
  DB) **resets on every rebuild/sleep**. Treat all data as disposable, or attach
  HF persistent storage and point `STORAGE_DIR` / `DATABASE_URL` at it.
- **Cold start.** On a GPU Space, first request downloads model weights — show a
  loading state and expect a delay (or bake weights into the image).

## Environment

`ENV`, `DATABASE_URL`, `STORAGE_DIR`, `ML_MODELS_DIR`, `FRONTEND_DIST`,
`CORS_ORIGINS`, `PIPELINE_BACKEND`, `JWT_SECRET` — see `backend/.env.example`.
The frontend is built same-origin (`NEXT_PUBLIC_API_BASE_URL=""`), so the UI and
API share the Space URL.
