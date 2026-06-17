# Combined single-container image for the Hugging Face Space demo:
# builds the Next.js static export, then runs FastAPI (serving API + SPA) plus
# the generation worker. Listens on 7860 (HF Spaces convention).
#
# Build:  docker build -t ai-avatar .
# Run:    docker run -p 7860:7860 -e JWT_SECRET=... ai-avatar

# ---- Stage 1: build the frontend as a static export -------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API calls (relative /api/...) — served by FastAPI in stage 2.
ENV NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_OUTPUT=export
RUN npm run build   # produces /fe/out

# ---- Stage 2: python runtime ------------------------------------------------
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# ffmpeg is required by both pipelines.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY backend/ /app/backend/
COPY ml_models/ /app/ml_models/
COPY scripts/ /app/scripts/
# Built SPA from stage 1.
COPY --from=frontend /fe/out /app/frontend/out

# Writable, ephemeral storage (HF Spaces filesystem resets on rebuild/sleep).
RUN mkdir -p /app/storage/uploads /app/storage/avatars /app/storage/voices /app/storage/outputs

ENV ENV=production \
    DATABASE_URL=sqlite:////app/storage/ai_avatar.db \
    STORAGE_DIR=/app/storage \
    ML_MODELS_DIR=/app/ml_models \
    FRONTEND_DIST=/app/frontend/out \
    CORS_ORIGINS=* \
    PIPELINE_BACKEND=auto \
    PORT=7860
EXPOSE 7860

CMD ["bash", "/app/scripts/start.sh"]
