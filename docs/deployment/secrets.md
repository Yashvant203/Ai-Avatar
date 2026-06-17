# Secrets & configuration

**Never commit secrets.** Source them from the platform's secret store
(HF Space Secrets, Kaggle Secrets, your host's env). `backend/.env.example` is
the canonical list of config keys; keep it in parity with `app/core/config.py`.

## Required / important secrets

| Key | Where | Notes |
|---|---|---|
| `JWT_SECRET` | **all environments** | Long random string. Production **refuses to boot** with the default or any value < 32 chars (`config.py` validator). Generate: `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `HF_TOKEN` | Kaggle/Space/host | Only if a model repo on Hugging Face is gated. Used by `download_models.py`. |
| `DATABASE_URL` | host | Defaults to local SQLite. For Pattern B use Postgres: `postgresql+psycopg://user:pass@host/db`. |

## Other config (non-secret, env-driven)

`ENV`, `STORAGE_DIR`, `ML_MODELS_DIR`, `FRONTEND_DIST`, `CORS_ORIGINS`,
`ACCESS_TTL`, `REFRESH_TTL`, `PIPELINE_BACKEND`, `MAX_UPLOAD_MB`,
`MIN/MAX_VIDEO_SECONDS`, `MAX_SCRIPT_CHARS`, `OUTPUT_FPS`, `WORKER_POLL_SECONDS`,
`JOB_HEARTBEAT_TIMEOUT`. See `backend/.env.example`.

## Setting secrets per platform

- **Hugging Face Space:** Settings → *Variables and secrets* → add as **Secret**
  (not a public variable) for `JWT_SECRET` / `HF_TOKEN`.
- **Kaggle:** Add-ons → *Secrets* → reference via
  `from kaggle_secrets import UserSecretsClient`.
- **Modal:** `modal secret create ai-avatar JWT_SECRET=… HF_TOKEN=…` and attach
  to the function.
- **Render/Railway/Fly:** the host's environment/secret settings.

## Hygiene

- The frontend's `NEXT_PUBLIC_*` vars are **baked into the client bundle at build
  time and are public** — never put secrets there. Only the API base URL lives
  there.
- Review deploy configs and notebooks for accidental secret leakage before
  pushing; run the `security-review` skill on any auth-touching change.
- `.gitignore` excludes `.env`, `*.db`, `storage/*`, and `ml_models/weights/*`;
  `.dockerignore` keeps them out of the image.
