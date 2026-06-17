# Alembic migrations

- `alembic upgrade head` — apply all migrations.
- `alembic downgrade base` — roll back to empty.
- `alembic revision --autogenerate -m "add users"` — generate a migration from model changes.

`env.py` pulls the DB URL from `app.core.config.Settings` and targets
`app.db.base.Base.metadata`. SQLite uses **batch mode** (`render_as_batch`) so
`ALTER TABLE` operations work despite SQLite's limitations.

Baseline migration `0001_baseline` is intentionally empty — real tables arrive
in Phase 2 (users) and Phase 3+ (avatars, videos, jobs).
