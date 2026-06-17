# Runbook

Operational guide for running, verifying, and troubleshooting a deployment.

## Start / stop

**Local (dev):**
```bash
make migrate        # alembic upgrade head
make dev-backend    # uvicorn :8000
make dev-worker     # generation worker
make dev-frontend   # next dev :3000
```

**Container (prod/demo):**
```bash
docker build -t ai-avatar .
docker run -p 7860:7860 -e JWT_SECRET="$(openssl rand -base64 48)" ai-avatar
# scripts/start.sh runs: migrate → worker (bg) → uvicorn (fg) on :7860
```
Stop: `Ctrl-C` / `docker stop` (SIGTERM is forwarded to the worker).

## Cold-start expectations

| Backend | First request | Notes |
|---|---|---|
| stub (CPU) | seconds | ffmpeg only; no weights |
| real (GPU) | minutes on first run | downloads weights, loads models into VRAM; kept warm after |

Show the UI's loading/progress states during cold start (already implemented).
Pre-bake or cache weights to cut this (see `kaggle.md`, `hf_spaces.md`).

## "Is it healthy?" checklist

```bash
curl -s $BASE/healthcheck                       # {"status":"ok","db":"ok"}
python scripts/smoke_test.py --base-url $BASE   # auth → avatar → (generate) → download
```
- API up + DB reachable → `/healthcheck` 200.
- Worker alive → enqueued jobs leave `queued` within a few seconds; `progress`
  advances; `heartbeat_at` updates.
- Storage writable → uploads succeed; `storage/outputs/{job}/output.mp4` appears.

## Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| Boot fails: "JWT_SECRET must be strong" | default/weak secret in `ENV=production` | set a ≥32-char `JWT_SECRET` |
| Jobs stuck in `processing`, no progress | worker crashed | the **zombie reaper** requeues after `JOB_HEARTBEAT_TIMEOUT` (300 s); ensure the worker is running |
| Jobs stuck in `queued` forever | worker not started | run `python -m worker.main` / check `scripts/start.sh` |
| `MODEL_OOM` in job error | GPU VRAM exhausted | smaller chunking; one model at a time; bigger GPU |
| Generate returns 409 | avatar not `ready` | finish avatar creation first (needs GPU for real backend) |
| Data gone after restart | **ephemeral storage** (HF Spaces) | expected on demo; use persistent storage / Pattern B |
| Weight download timeout | slow/gated HF pull on cold start | set `HF_TOKEN`; pre-cache weights; retry |
| `ffmpeg not found` | image missing ffmpeg | `setup_ffmpeg.sh`; the Dockerfile installs it |
| Upload 413 | file over `MAX_UPLOAD_MB` | raise the limit or shrink the clip; add a reverse-proxy body cap in prod |

## Rollback

- **HF Space:** redeploy a previous commit/tag (Space rebuilds from git).
- **Container:** run the previously tagged image.
- **DB migrations:** `alembic downgrade <rev>` (SQLite uses batch mode). Take a
  copy of the SQLite file / a Postgres snapshot before migrating in prod.

## Scaling notes

- Concurrency is **1 worker** by design (single GPU). For more throughput, run
  multiple workers against a **shared** Postgres queue (the atomic claim in
  `app/queue/db_queue.py` is safe for >1 worker) + shared object storage. See
  `free_gpu_options.md` Pattern B.
