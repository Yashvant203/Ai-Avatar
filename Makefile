# AI Avatar Platform — developer tasks
# Usage: make <target>

BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/.venv
PY       := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help
help: ## List available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create venv, install backend + frontend deps
	python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "$(BACKEND)[dev]"
	cd $(FRONTEND) && npm install

.PHONY: dev-backend
dev-backend: ## Run FastAPI with autoreload
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run Next.js dev server
	cd $(FRONTEND) && npm run dev

.PHONY: dev-worker
dev-worker: ## Run the background job worker (added in Phase 4)
	cd $(BACKEND) && .venv/bin/python -m app.worker

.PHONY: migrate
migrate: ## Apply Alembic migrations to head
	cd $(BACKEND) && .venv/bin/alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision m="message"
	cd $(BACKEND) && .venv/bin/alembic revision --autogenerate -m "$(m)"

.PHONY: lint
lint: ## Lint backend (ruff) + frontend (eslint)
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/black --check .
	cd $(FRONTEND) && npm run lint

.PHONY: format
format: ## Auto-format backend (ruff+black) + frontend (prettier)
	cd $(BACKEND) && .venv/bin/ruff check --fix . && .venv/bin/black .
	cd $(FRONTEND) && npm run format

.PHONY: test
test: ## Run backend tests
	cd $(BACKEND) && .venv/bin/pytest -q

.PHONY: download-models
download-models: ## Download F5-TTS / MuseTalk / LivePortrait weights
	$(PY) ml_models/download_models.py

.PHONY: verify-env
verify-env: ## Assert GPU, ffmpeg, and model weights are present
	$(PY) ml_models/verify_env.py
