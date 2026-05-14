# Multi-stage image: eqlib from repo + studio backend
# Stage 1: build the application
FROM python:3.11-slim AS base

WORKDIR /app
RUN pip install --no-cache-dir -U pip

# EasyQuant core
COPY pyproject.toml README.md /app/
COPY eqlib /app/eqlib
RUN pip install --no-cache-dir -e .

# Studio API
COPY web_strategy_studio/backend /app/web_strategy_studio/backend
WORKDIR /app/web_strategy_studio/backend
RUN pip install --no-cache-dir -e .

# S7: Create a non-root user for runtime security.
# The data directory is owned by this user so the process can write artifacts.
RUN useradd -m -u 1000 studio && mkdir -p /data/artifacts/reports && chown -R studio:studio /data

ENV EQ_STUDIO_REPO_ROOT=/app
ENV EQ_STUDIO_ARTIFACT_DIR=/data/artifacts
ENV EQ_STUDIO_DATABASE_URL=sqlite+aiosqlite:////data/studio.sqlite3

USER studio

EXPOSE 8080

# S7: Add a healthcheck so orchestrators (Docker Compose, Kubernetes) can
# detect when the service is unhealthy and restart it automatically.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/healthz')" || exit 1

CMD ["python", "-m", "uvicorn", "studio_api.app:app", "--host", "0.0.0.0", "--port", "8080"]
