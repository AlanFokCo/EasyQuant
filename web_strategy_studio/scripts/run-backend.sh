#!/usr/bin/env bash
# Start FastAPI (uvicorn) from web_strategy_studio/backend with EQ_STUDIO_REPO_ROOT
# defaulting to the EasyQuant repo root (parent of web_strategy_studio/).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDIO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${STUDIO_ROOT}/.." && pwd)"
export EQ_STUDIO_REPO_ROOT="${EQ_STUDIO_REPO_ROOT:-${REPO_ROOT}}"

PORT="${EQ_STUDIO_UVICORN_PORT:-8080}"

cd "${STUDIO_ROOT}/backend"
exec python -m uvicorn studio_api.app:app --reload --host 127.0.0.1 --port "${PORT}"
