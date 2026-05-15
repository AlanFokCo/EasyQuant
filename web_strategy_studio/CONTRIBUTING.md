# Contributing to EasyQuant Web Strategy Studio

> **Scope:** This guide covers the `web_strategy_studio/` sub-project — the FastAPI backend and React frontend. For contributions to `eqlib/` (the core backtesting library), see [`CONTRIBUTING.md`](../CONTRIBUTING.md) in the repository root.

---

## Table of Contents

1. [Local Setup](#1-local-setup)
2. [Project Layout](#2-project-layout)
3. [Running Locally](#3-running-locally)
4. [Adding a Backend Route](#4-adding-a-backend-route)
5. [Writing Alembic Migrations](#5-writing-alembic-migrations)
6. [Regenerating the Symbols File](#6-regenerating-the-symbols-file)
7. [Writing Backend Tests](#7-writing-backend-tests)
8. [Frontend Development](#8-frontend-development)
9. [Code Style & Linting](#9-code-style--linting)
10. [Docker](#10-docker)
11. [CI](#11-ci)

---

## 1. Local Setup

**Prerequisites:** Python 3.10+, Node.js 18+, npm 9+.

```bash
# Clone the repo
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant

# Install eqlib (required by the backend worker)
pip install -e .

# Install backend (editable) + dev tools
cd web_strategy_studio/backend
pip install -e ".[dev]"
cd ../..

# Install frontend + build the symbol manifest
cd web_strategy_studio
npm run install:all   # installs root + frontend + runs build_symbols.py
cd ..

# (optional) Install pre-commit hooks
pip install pre-commit
pre-commit install
```

---

## 2. Project Layout

```
web_strategy_studio/
├── backend/
│   ├── studio_api/          # FastAPI application package
│   │   ├── app.py           # ASGI app + lifespan
│   │   ├── config.py        # Pydantic settings (env-vars)
│   │   ├── db.py            # Async SQLAlchemy engine + session factory
│   │   ├── models.py        # ORM models (Strategy, Run, …)
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   ├── routers/         # One file per domain (strategies, runs, …)
│   │   ├── run_queue.py     # In-process run queue (asyncio)
│   │   ├── stream_hub.py    # SSE broadcast hub with replay ring-buffer
│   │   ├── backtest_executor.py  # Subprocess driver
│   │   └── isolated_runner.py   # Subprocess entry point
│   ├── alembic/             # Database migrations
│   ├── alembic.ini
│   ├── tests/               # pytest test suite
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/             # Typed API client (fetch wrappers)
│   │   ├── components/      # React components (<250 lines each)
│   │   ├── hooks/           # Custom React hooks
│   │   ├── pages/           # Route-level pages
│   │   └── store/           # Zustand global stores
│   ├── eslint.config.js
│   ├── .prettierrc
│   └── package.json
├── scripts/
│   ├── build_symbols.py     # Generates eqlib_symbols.json for autocomplete
│   └── run-backend.sh       # Dev-mode backend launcher
├── Dockerfile               # Multi-stage: frontend-builder → api → nginx
├── docker-compose.yml
├── nginx.conf
└── CONTRIBUTING.md          # ← you are here
```

---

## 3. Running Locally

```bash
cd web_strategy_studio
npm run dev:all
```

This starts:
- **API** on `http://localhost:8080` (uvicorn, auto-reload)
- **Frontend** on `http://localhost:5173` (Vite, HMR)

Vite proxies `/api/*` and `/static/*` to the API server — the browser always talks to port 5173.

To start each piece independently:

```bash
# Backend only
cd web_strategy_studio/backend
uvicorn studio_api.app:app --reload --port 8080

# Frontend only
cd web_strategy_studio/frontend
npm run dev
```

---

## 4. Adding a Backend Route

1. **Choose or create a router file** in `studio_api/routers/`.  
   Each file has an `APIRouter(prefix="/api/v1", tags=["domain"])`.

2. **Add request/response schemas** to `studio_api/schemas.py`.

3. **Register the router** in `studio_api/app.py`:
   ```python
   from studio_api.routers import my_router
   app.include_router(my_router.router)
   ```

4. **Write a test** — see [§7 Writing Backend Tests](#7-writing-backend-tests).

5. If the route touches the database schema, **write a migration** — see [§5](#5-writing-alembic-migrations).

### Naming conventions

| Concern | Convention |
|---------|-----------|
| HTTP verbs | Follow REST: `GET` list/get, `POST` create, `PATCH` update, `DELETE` delete |
| Path params | snake_case: `/strategies/{strategy_id}` |
| Error responses | Use `api_error(code, message)` from `schemas.py`; always raise `HTTPException` |
| Response models | Always declare `response_model=` on every endpoint |
| DB session | Inject via `session: AsyncSession = Depends(get_session)` |

---

## 5. Writing Alembic Migrations

The database is SQLite in development and should remain migration-compatible with PostgreSQL.

```bash
cd web_strategy_studio/backend

# Auto-generate a migration from model changes
alembic revision --autogenerate -m "add_param_sets_table"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

**Rules:**
- Do not use SQLite-only DDL (e.g. `PRAGMA`). Stick to standard SQL.
- Always review the generated file before committing — autogenerate can miss renames or type changes.
- Migrations live in `alembic/versions/`. Commit the generated file alongside the model change.

---

## 6. Regenerating the Symbols File

The Monaco editor autocomplete is powered by a pre-built symbol manifest. Regenerate it any time `eqlib`'s public API changes:

```bash
python web_strategy_studio/scripts/build_symbols.py
```

The output is committed to `backend/studio_api/data/eqlib_symbols.json`. The CI workflow will fail if the symbols file is stale relative to the installed `eqlib` (run `build_symbols.py` and commit the diff).

---

## 7. Writing Backend Tests

Tests live in `web_strategy_studio/backend/tests/`. Run them with:

```bash
cd web_strategy_studio/backend
pytest tests/ -v --tb=short
```

### Test structure

```python
import os
import pytest

# Point at in-memory DB before importing studio_api
os.environ.setdefault("EQ_STUDIO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("EQ_STUDIO_ARTIFACT_DIR", "/tmp/eq_studio_test")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from studio_api.app import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_my_endpoint(client):
    resp = client.get("/api/v1/my-endpoint")
    assert resp.status_code == 200
```

**Guidelines:**
- Use `scope="module"` for the `TestClient` fixture to avoid repeated DB init overhead.
- Use `EQ_STUDIO_DATABASE_URL=sqlite+aiosqlite:///:memory:` — never touch a real database in tests.
- Each regression for a known bug gets a comment `# B<N>: <bug description>`.

---

## 8. Frontend Development

```bash
cd web_strategy_studio/frontend
npm run dev          # start Vite dev server
npm run typecheck    # tsc --noEmit
npm run lint:eslint  # ESLint
npm run lint:prettier # Prettier check
npm run format       # Prettier write
npm run test         # vitest unit tests
```

### Adding a component

1. Create `src/components/MyComponent.tsx` (keep it < 250 lines).
2. Export the component as a named export.
3. State: prefer local `useState`; use Zustand (`src/store/`) for cross-component state.
4. API calls: add a typed fetch function to `src/api/client.ts`.
5. Style: use CSS custom properties defined in `src/index.css`; avoid inline styles for anything other than dynamic values.

### Adding a page/route

1. Create `src/pages/MyPage.tsx`.
2. Add a lazy-loaded `<Route>` in `src/App.tsx`.

---

## 9. Code Style & Linting

### Backend (Python)

| Tool | Role |
|------|------|
| `ruff` | Lint + import sort (auto-fix with `ruff --fix`) |
| `black` | Format |
| `mypy` | Type check (lenient mode; tighten incrementally) |

Config lives in `web_strategy_studio/backend/pyproject.toml`.

```bash
cd web_strategy_studio/backend
ruff check . --fix
black .
mypy studio_api/
```

### Frontend (TypeScript / React)

| Tool | Role |
|------|------|
| ESLint | Lint, including `react-hooks/rules-of-hooks` and `react-hooks/exhaustive-deps` |
| Prettier | Format |
| TypeScript strict mode | Type safety |

```bash
cd web_strategy_studio/frontend
npm run lint:eslint
npm run format
npm run typecheck
```

### Pre-commit hooks

Install once:

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

---

## 10. Docker

Build and run the full stack locally with Docker Compose:

```bash
cd web_strategy_studio
docker compose up --build
```

This builds three stages from `Dockerfile`:

| Stage | Purpose |
|-------|---------|
| `frontend-builder` | `npm run build` → `dist/` |
| `api` | eqlib + FastAPI server on port 8080 (internal) |
| `nginx` | Serves `dist/`, proxies `/api` and `/static` to `api:8080`, exposed on host port 8080 |

The app is then available at `http://localhost:8080`.

To build only the API image:

```bash
docker build --target api -f web_strategy_studio/Dockerfile .
```

---

## 11. CI

The **`studio-test`** workflow (`.github/workflows/studio-test.yml`) runs on every push or PR that touches `web_strategy_studio/`:

| Job | Steps |
|-----|-------|
| `backend` (Python 3.10 & 3.11) | `ruff check`, `black --check`, `pytest tests/` |
| `frontend` | `tsc --noEmit`, `eslint src`, `vitest run` |
| `e2e` (optional, disabled) | Playwright golden-path smoke test |

**All jobs must be green before merging.**
