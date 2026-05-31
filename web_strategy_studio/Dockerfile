# Multi-stage image:
#   stage 1 (frontend-builder) — builds React app via Vite
#   stage 2 (api)              — eqlib + studio FastAPI server
#   stage 3 (nginx)            — serves static dist/ and reverse-proxies /api + /static

# ---------------------------------------------------------------------------
# Stage 1: build frontend (使用阿里云镜像)
# ---------------------------------------------------------------------------
FROM dockerpull.org/library/node:20-slim AS frontend-builder

WORKDIR /build

# 使用淘宝 npm 镜像
RUN npm config set registry https://registry.npmmirror.com

# Install monorepo root deps (concurrently only)
COPY web_strategy_studio/package.json web_strategy_studio/package-lock.json* ./
RUN npm ci --ignore-scripts

# Install and build frontend
COPY web_strategy_studio/frontend ./frontend
RUN cd frontend && npm ci && npm run build

# ---------------------------------------------------------------------------
# Stage 2: API (使用阿里云镜像)
# ---------------------------------------------------------------------------
FROM dockerpull.org/library/python:3.11-slim AS api

WORKDIR /app

# 使用阿里云 pip 镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -U pip

# EasyQuant core
COPY pyproject.toml README.md /app/
COPY eqlib /app/eqlib
RUN pip install --no-cache-dir -e .

# Studio API
COPY web_strategy_studio/backend /app/web_strategy_studio/backend
WORKDIR /app/web_strategy_studio/backend
RUN pip install --no-cache-dir -e .

# S7: Create a non-root user for runtime security.
RUN useradd -m -u 1000 studio && mkdir -p /data/artifacts/reports && chown -R studio:studio /data

ENV EQ_STUDIO_REPO_ROOT=/app
ENV EQ_STUDIO_ARTIFACT_DIR=/data/artifacts
ENV EQ_STUDIO_DATABASE_URL=sqlite+aiosqlite:////data/studio.sqlite3

USER studio

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/healthz')" || exit 1

CMD ["python", "-m", "uvicorn", "studio_api.app:app", "--host", "0.0.0.0", "--port", "8080"]

# ---------------------------------------------------------------------------
# Stage 3: nginx (使用阿里云镜像)
# ---------------------------------------------------------------------------
FROM dockerpull.org/library/nginx:1.27-alpine AS nginx

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy built frontend assets
COPY --from=frontend-builder /build/frontend/dist /usr/share/nginx/html

# nginx config: serve SPA + proxy /api and /static to upstream api service
COPY web_strategy_studio/nginx.conf /etc/nginx/conf.d/studio.conf

EXPOSE 80

