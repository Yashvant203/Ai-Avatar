# Hugging Face Spaces — demo hosting

The repo ships a **combined Docker image** (`Dockerfile`) that runs the FastAPI
API, serves the static Next.js UI same-origin, and runs the generation worker —
all on port **7860**. This is the easiest way to put a public, always-on demo
online.

## Deploy

1. Create a new **Space** → SDK: **Docker**.
2. Push this repo to the Space (or connect the GitHub repo). HF builds the
   `Dockerfile` automatically. Copy `README_HF.md` → the Space's `README.md`
   (its YAML frontmatter sets `sdk: docker`, `app_port: 7860`).
3. **Settings → Variables and secrets** → add:
   - `JWT_SECRET` = a long random string (the app refuses to boot in production
     with the default/weak secret).
   - `HF_TOKEN` = only if pulling gated weights.
4. The Space boots via `scripts/start.sh` (migrate → worker → uvicorn).

## Choose the profile

| Profile | Hardware | ML | Use |
|---|---|---|---|
| **CPU demo** (default) | free CPU | `PIPELINE_BACKEND` auto → **stub** | Show the full UX; placeholder MP4s |
| **GPU Space** | paid GPU | real F5-TTS/LivePortrait/MuseTalk | Real cloned-voice talking heads |
| **ZeroGPU** | free A100 slice (queued) | real, per-call | Free real generation w/ queue latency |

For an MVP demo, the **CPU demo** profile is recommended: it exercises signup,
avatar creation flow, queueing, progress, and download end-to-end without a GPU.

## Limitations (and how this repo handles them)

- **Ephemeral storage.** The Space filesystem — including `storage/` and the
  SQLite DB at `/app/storage/ai_avatar.db` — **resets on every rebuild and on
  sleep/wake.** All users/avatars/videos are lost. For a demo that's fine
  (disposable). To persist: enable HF **persistent storage** and set
  `STORAGE_DIR` + `DATABASE_URL` to the mounted path, or move to Pattern B
  (external Postgres + object storage — see `free_gpu_options.md`).
- **Real ML needs a GPU.** On CPU the app auto-selects the **stub** backend, so
  generated videos are real files but not real cloned avatars. Set
  `PIPELINE_BACKEND=real` only on a GPU Space with weights present.
- **Cold-start weight download.** On a GPU Space, the first generation pulls
  model weights and can exceed a request timeout. Mitigate by baking weights
  into the image, using HF persistent storage for the HF cache, and showing the
  UI's loading/progress states (already implemented).
- **Single small container.** Concurrency is 1 (one worker). Fine for a demo;
  scale via Pattern B.

## Verify a deployment

```bash
python scripts/smoke_test.py --base-url https://<user>-<space>.hf.space
```
On a CPU demo this confirms health + auth + avatar + that `generate` correctly
rejects a not-yet-ready avatar (409). On a GPU Space with a ready avatar it runs
the full generate → download path.
