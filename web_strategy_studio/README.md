# Web Strategy Studio

在浏览器中编辑基于 **eqlib** 的 Python 策略、运行静态检查、异步回测，并通过 **SSE** 查看日志与进度；完成后打开与 `generate_html_report` 风格一致的 HTML 报告。

- **设计规格（权威）**：仓库根目录 [`doc/design_spec_web_strategy_studio.md`](../doc/design_spec_web_strategy_studio.md)
- **本目录**：`web_strategy_studio/` — 前后端 monorepo（`backend/` + `frontend/`），不修改 `eqlib/` 核心库；回测在 **子进程** 中通过 `studio_api.isolated_runner` 调用 `run_backtest` 与 `generate_html_report`。

## 架构概览

| 组件 | 技术 | 说明 |
|------|------|------|
| `backend/` | FastAPI、SQLAlchemy 2（async）、SQLite（默认）、Ruff、Black | REST `/api/v1/*`、SSE `/api/v1/runs/{id}/stream`、静态报告 `/static/reports/` |
| `frontend/` | React 18、TypeScript、Vite、Monaco、TanStack Query、Zustand、react-virtuoso | 70/30 布局、设计 token 对齐 HTML 报告（§2.2） |
| 执行层 | `asyncio` 子进程 + 可选 `proc_registry` 取消 | MVP 进程内队列；接口可替换为 Redis Worker |

## 环境要求

- Python **3.9+**（与根目录 `eqlib` 的 `requires-python` 一致；推荐 3.11）
- Node **18+**（推荐 **20 LTS**；Vite 5 在 Node 16 及以下会启动失败，例如 `crypto.getRandomValues is not a function`）。本目录提供 **`.nvmrc`**（内容为 `20`），使用 nvm 时可执行：`nvm install && nvm use`。
- 已安装 **EasyQuant / eqlib**（回测依赖 `akshare` 等）：在仓库根目录执行 `pip install -e .`

## 环境变量（后端）

与规格书 §8.2 对齐（通过 `pydantic-settings`，前缀 `EQ_STUDIO_`）：

| 变量 | 说明 | 默认 |
|------|------|------|
| `EQ_STUDIO_DATABASE_URL` | SQLAlchemy 异步 DSN | `sqlite+aiosqlite:///./studio.sqlite3`（相对后端工作目录） |
| `EQ_STUDIO_ARTIFACT_DIR` | 报告与产物根目录 | `./artifacts` |
| `EQ_STUDIO_PUBLIC_BASE_URL` | 生成绝对 URL 时的前缀（可选） | 空 |
| `EQ_STUDIO_RUN_TIMEOUT_SEC` | 单任务墙钟超时（秒） | `900` |
| `EQ_STUDIO_MAX_MEMORY_MB` | 预留；完全 cgroup 限内存需 Linux/容器 | `2048` |
| `EQ_STUDIO_ENABLE_NETWORK` | 文档占位；MVP 未强制禁网 | `false` |
| `EQ_STUDIO_REPO_ROOT` | **eqlib 仓库根路径**（含 `eqlib/` 包） | 后端默认由 `config.py` 相对路径解析为仓库根；`npm run dev:all` 时由 `scripts/run-backend.sh` 设为 **`web_strategy_studio` 的上一级目录**（与默认推断一致） |
| `EQ_STUDIO_UVICORN_PORT` | 本地 **uvicorn** 监听端口（与 Vite `proxy` 一致） | `8080` |

## 本地开发

### 一条命令同时跑前后端（推荐，无 Docker）

用于本机联调：后端 **uvicorn** 监听 `127.0.0.1:8080`，前端 **Vite** 开发服务器（一般为 `5173`），`Ctrl+C` 一次结束两个进程。

**一次性准备**（仓库根已 `pip install -e .`，且后端包已装）：

```bash
cd /path/to/EasyQuant/web_strategy_studio
npm run install:all
# 若尚未安装 studio 后端 Python 包，仍在仓库根执行过 pip install -e . 后：
#   cd web_strategy_studio/backend && pip install -e .
```

**每次开发**：

```bash
cd /path/to/EasyQuant/web_strategy_studio
npm run dev:all
```

说明：

- 后端工作目录为 `web_strategy_studio/backend`；环境变量 **`EQ_STUDIO_REPO_ROOT`** 默认设为 **EasyQuant 仓库根**（`web_strategy_studio` 的上一级，由 `scripts/run-backend.sh` 根据脚本位置解析）。若需覆盖可在外层 `export EQ_STUDIO_REPO_ROOT=/path/to/EasyQuant` 后再执行 `npm run dev:all`。
- 前端由 `npm run dev --prefix ./frontend` 启动，等价于在 `frontend/` 下执行 `npm run dev`。
- **macOS / Linux**：依赖 Bash 与 `concurrently`（由本目录 `npm install` 安装）。**Windows**：未做原生批处理封装；可用 **WSL / Git Bash** 运行上述命令，或分别开两个终端按下方「分步」启动。

与 **Docker** 方式并存：本地一条命令路径见本节；容器部署仍见下文「Docker（可选）」。

### 端口被占用（`Address already in use`）

默认后端使用 **8080**。若报错 `[Errno 48] Address already in use`，说明本机 **8080 已被占用**（例如之前未退出的 uvicorn、其他应用）。

任选其一：

1. **释放 8080**（macOS 示例）：
   ```bash
   lsof -ti :8080 | xargs kill
   ```
   确认无敏感进程后再执行；必要时用 `lsof -i :8080` 查看占用者。

2. **改用其他端口**（前后端会读同一环境变量）：
   ```bash
   export EQ_STUDIO_UVICORN_PORT=8081
   npm run dev:all
   ```
   或一行：`EQ_STUDIO_UVICORN_PORT=8081 npm run dev:all`

### 前端报错 `crypto.getRandomValues is not a function`

说明当前 **Node 版本过低**（常见为 16 及以下）。Vite 5 需要 **Node 18+**。

- 用 **nvm**：`cd web_strategy_studio && nvm install && nvm use`（读取 `.nvmrc` 中的 `20`），再执行 `npm run dev:all`。
- 或安装 **Node 20 LTS** 后重新打开终端，确认 `node -v` 为 `v18` / `v20` 等。

根目录 `npm run dev:all` 前会自动执行 `predev:all`：若 Node 不达标会直接退出并打印中文提示，避免先起后端再因 Vite 失败而整组被 `concurrently` 杀掉。

### 回测日志里 `result.json` / `'str' object has no attribute 'dumps'`（仍跑的是旧包）

说明 **子进程里的 `studio_api` 来自 Anaconda 的 `site-packages`**，不是本仓库里刚改的代码。请先确认路径：

```bash
python -c "import studio_api.isolated_runner as m; print(m.__file__)"
```

- **正确**：应包含 `EasyQuant/web_strategy_studio/backend/studio_api/isolated_runner.py`（editable 指向本仓库）。
- **错误**：若在 `.../anaconda3/lib/python3.9/site-packages/studio_api/...`，请在本仓库 **重装后端**（用你实际用来启动 uvicorn 的那个 `python` / `pip`）：

```bash
# 建议先卸掉旧安装，避免混用
pip uninstall eq-studio-api -y

cd /path/to/EasyQuant/web_strategy_studio/backend
# 若 `pip install -e .` 报 “editable mode … setup.py not found”，先升级 pip/setuptools，或本目录已提供 setup.py 兼容旧版 conda pip：
python -m pip install --upgrade "pip>=22" "setuptools>=68" wheel
pip install -e .
```

然后 **完全退出并重启** `npm run dev:all`（或重启 uvicorn），再跑一次回测。当前包版本在 `backend/pyproject.toml` 的 `version` 字段（例如 `0.1.1`），可用 `pip show eq-studio-api` 对照。

**查看报告**：回测成功后，Studio 弹窗内会 **嵌入预览** HTML（通过 `http(s)://…/static/reports/{run_id}/report.html`，由 Vite 代理或 `VITE_API_ORIGIN` 指向 API）；也可点「新标签打开」。无需使用 `file://` 或磁盘绝对路径。

### 1. 安装后端

```bash
cd /path/to/EasyQuant
pip install -e .

cd web_strategy_studio/backend
pip install -e .
```

### 2. 启动 API（默认 `http://127.0.0.1:8080`）

```bash
# 仍在 web_strategy_studio/backend 下
python -m uvicorn studio_api.app:app --reload --host 127.0.0.1 --port 8080
```

健康检查：`GET http://127.0.0.1:8080/api/v1/healthz`  
指标占位：`GET http://127.0.0.1:8080/api/v1/metrics`

### 3. 安装并启动前端

```bash
cd web_strategy_studio/frontend
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（一般为 `http://127.0.0.1:5173`）。开发模式下通过 Vite **proxy** 转发 `/api` 与 `/static` 到后端。

若前后端域名不同（生产环境），设置：

```bash
# frontend/.env.production 示例
VITE_API_ORIGIN=https://your-api-host
```

### 4. 生产构建（前端静态资源）

```bash
cd web_strategy_studio/frontend
npm run build
# 产物在 frontend/dist/，可由任意静态服务器或 Nginx 托管；/api 反向代理到 FastAPI。
```

## Docker（可选）

在 **仓库根目录**：

```bash
docker compose -f web_strategy_studio/docker-compose.yml build
docker compose -f web_strategy_studio/docker-compose.yml up -d
```

当前 `Dockerfile` 构建 **仅 API** 镜像（内置安装根目录 `eqlib` + studio backend）。前端静态资源与 Nginx 合并路由可作为后续迭代。

## API 摘要

- `POST /api/v1/strategies`、`GET/PATCH /api/v1/strategies/{id}`、`GET .../template`
- `POST /api/v1/lint`、`POST /api/v1/strategies/{id}/lint`
- `POST /api/v1/format`（Black）
- `POST /api/v1/runs`（`202` + `Idempotency-Key` 占位）、`GET .../runs/{id}`、`POST .../cancel`
- `GET /api/v1/runs/{id}/stream`（**SSE**：`log` / `progress` / `done` / `error`）
- `POST /api/v1/completion`（基于 `eqlib_symbols.json` 的 MVP 符号过滤）

## 已知限制 / 后续工作

- **沙箱**：MVP 为子进程 + 静态 AST 黑名单 + 超时；生产级 cgroup / `network: none` / 每任务容器见规格 §7.5。
- **Redis / PostgreSQL**：配置项已预留；当前默认 SQLite + 进程内 `BackgroundTasks`。
- **严格模式 mypy**：`lint` 的 `profile=strict` 尚未接 mypy。
- **前端 ESLint**：未配置；使用 `npm run lint`（`tsc --noEmit`）做类型检查。

## 相关文档

- [Design Spec — Web 策略工作室](../doc/design_spec_web_strategy_studio.md)
