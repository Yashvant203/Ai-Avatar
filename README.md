# AI Avatar Platform

Self-hosted platform that turns one short video into a **reusable talking-head
avatar**, then generates new videos from any script — in the subject's cloned
voice, with lip-sync. **Open-source models only.** No HeyGen, Synthesia, or D-ID.

> Pipeline models: **F5-TTS** (voice cloning) · **LivePortrait** (head/expression
> animation) · **MuseTalk** (lip-sync) · **ffmpeg** (mux).

## Repository layout

```
AI-AVATAR/
├── frontend/      # Next.js 15 + TypeScript + Tailwind (neo-brutalism design)
├── backend/       # FastAPI + SQLAlchemy + Alembic (SQLite)
├── storage/       # local filesystem artifacts (uploads, avatars, voices, outputs)
├── ml_models/     # weight download + environment verification scripts
├── docs/          # the 6 design specs (PRD, architecture, schema, pipelines, roadmap)
└── Makefile       # dev task runner
```

## Quickstart

Prereqs: Python 3.10+, Node 20+, ffmpeg, and (for generation) a CUDA GPU.

```bash
# One-shot setup: venv + backend deps + frontend deps
make setup

# Backend  → http://localhost:8000  (docs at /docs, probe at /healthcheck)
cp backend/.env.example backend/.env       # then edit JWT_SECRET etc.
make migrate
make dev-backend

# Frontend → http://localhost:3000
cp frontend/.env.local.example frontend/.env.local
make dev-frontend
```

Model weights (run in the GPU/runtime env, e.g. Kaggle):

```bash
bash ml_models/setup_ffmpeg.sh
python ml_models/download_models.py
python ml_models/verify_env.py
make verify-env
```

## Common tasks

| Command            | Purpose                                            |
|--------------------|----------------------------------------------------|
| `make dev-backend` | FastAPI with autoreload                            |
| `make dev-frontend`| Next.js dev server                                 |
| `make migrate`     | Apply Alembic migrations                           |
| `make revision m=…`| Autogenerate a migration                           |
| `make lint`        | ruff + black --check (backend), eslint (frontend)  |
| `make format`      | Auto-format both stacks                            |
| `make test`        | Backend pytest                                     |

## Build status (Phase 1 — Foundation)

- ✅ Monorepo layout + tooling (Makefile, editorconfig, CI)
- ✅ FastAPI skeleton — `GET /healthcheck` returns `{status, version, db}`
- ✅ SQLite + SQLAlchemy + Alembic baseline (`upgrade head` / `downgrade base`)
- ✅ Next.js 15 neo-brutalism design system + landing page
- ✅ `ml_models/` download + verify scripts

See `docs/IMPLEMENTATION_ROADMAP.md` for the full phased plan. Phase 2
(Authentication) is next.

## Ethics & consent

Cloning a real person's face or voice requires that person's **explicit
consent**. Review model licenses in `ml_models/README.md` and the consent
requirements in `docs/PRODUCT_REQUIREMENTS.md` before deploying.

## License

MIT for the platform code (see `LICENSE`). Model weights carry their own
licenses — review before use.
