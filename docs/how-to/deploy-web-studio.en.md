# Deploying Web Strategy Studio

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Start locally or deploy Web Strategy Studio to production |
    | **Prerequisite** | [Install eqlib](install.md) |

---

## Quick Start

```bash
cd /path/to/EasyQuant
npm run dev:all
```

Then open `http://localhost:5173/` in your browser.

---

## Environment Setup

### Prerequisites

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | **3.9+** (3.11 recommended) | Must match eqlib's `requires-python` |
| Node | **18+** (20 LTS recommended) | Vite 5 is incompatible with Node 16 and below |
| pip package | `eqlib` | `pip install easyquant-eqlib` (PyPI) or `pip install -e .` from the repo root (source) |

If you use nvm to manage Node versions, run `nvm install && nvm use` in the studio directory (reads `20` from `.nvmrc`).

### One-Command Start (Recommended)

```bash
cd /path/to/EasyQuant/web_strategy_studio
npm run install:all   # First run: install frontend/backend deps + build symbol manifest
npm run dev:all       # Start backend uvicorn (:8080) + frontend Vite (:5173)
```

`dev:all` uses `concurrently` to launch both processes simultaneously. Press `Ctrl+C` once to stop them all.

### Step-by-Step Start

To start only one side:

```bash
# 1. Install backend
cd /path/to/EasyQuant
pip install -e .

cd web_strategy_studio/backend
pip install -e .

# 2. Start the API (default 127.0.0.1:8080)
python -m uvicorn studio_api.app:app --reload --host 127.0.0.1 --port 8080
```

```bash
# 3. Install and start the frontend
cd web_strategy_studio/frontend
npm install
npm run dev
```

Then open `http://localhost:5173/` in your browser.

### Environment Variables

The backend reads environment variables via `pydantic-settings` (prefix `EQ_STUDIO_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `EQ_STUDIO_DATABASE_URL` | SQLAlchemy async DSN | `sqlite+aiosqlite:///./studio.sqlite3` |
| `EQ_STUDIO_ARTIFACT_DIR` | Reports and artifacts directory | `<repo root>/artifacts` |
| `EQ_STUDIO_REPO_ROOT` | EasyQuant repo root path | Auto-detected by `config.py` |
| `EQ_STUDIO_RUN_TIMEOUT_SEC` | Per-task timeout (seconds) | `900` |
| `EQ_STUDIO_UVICORN_PORT` | Backend listen port | `8080` |
| `EQ_STUDIO_MAX_CONCURRENT_RUNS` | Max concurrent backtests | `2` |

In production, if the frontend and backend are not on the same domain, configure the frontend:

```bash
# frontend/.env.production
VITE_API_ORIGIN=https://your-api-host
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `Address already in use` (port 8080) | `lsof -ti :8080 \| xargs kill`, or `EQ_STUDIO_UVICORN_PORT=8081 npm run dev:all` |
| `crypto.getRandomValues is not a function` | Node version too old; upgrade to 18+ |
| Subprocess imports the wrong `studio_api` package | `pip uninstall eq-studio-api -y`, then `pip install -e .` again in this directory |
| macOS / Windows compatibility | macOS/Linux: use `npm run dev:all` directly; Windows: use WSL / Git Bash |

---

## Deployment Methods

### Docker Compose

Run from the repo root:

```bash
cd /path/to/EasyQuant
docker compose -f web_strategy_studio/docker-compose.yml build
docker compose -f web_strategy_studio/docker-compose.yml up -d
```

Compose builds two services:

| Service | Description |
|---------|-------------|
| `api` | FastAPI + eqlib, listens on internal port 8080 |
| `nginx` | Frontend static assets + reverse proxy for `/api` and `/static`, exposes port 8080 |

Data is persisted via the `studio-data` volume, which contains the SQLite database and backtest reports.

### Production Build (Static Frontend Hosting)

If you already have a web server, simply:

```bash
# Build frontend static assets
cd web_strategy_studio/frontend
npm run build
# Output in frontend/dist/

# Deploy backend separately (any WSGI/ASGI host)
cd web_strategy_studio/backend
pip install -e .
uvicorn studio_api.app:app --host 0.0.0.0 --port 8080 --workers 1
```

Nginx configuration example (frontend static assets + `/api` reverse proxy):

```nginx
server {
    listen 80;
    server_name studio.example.com;

    # Frontend SPA
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy
    location /api {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static reports
    location /static {
        proxy_pass http://127.0.0.1:8080;
    }
}
```
