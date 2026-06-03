# 部署 Web 策略工作室

!!! abstract "本篇导览"

    | 项目 | 说明 |
    |------|------|
    | **目标** | 本地启动或生产部署 Web 策略工作室 |
    | **前置** | [安装 eqlib](install.md) |

---

## 快速启动

```bash
cd /path/to/EasyQuant
npm run dev:all
```

然后在浏览器中打开 `http://localhost:5173/`。

---

## 环境搭建

### 前置要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | **3.9+**（推荐 3.11） | 与 eqlib 的 `requires-python` 一致 |
| Node | **18+**（推荐 20 LTS） | Vite 5 不兼容 Node 16 及以下 |
| pip 包 | `eqlib` | `pip install easyquant-eqlib`（PyPI）或在仓库根目录执行 `pip install -e .`（源码） |

若使用 nvm 管理 Node 版本，可在工作室目录执行 `nvm install && nvm use`（读取 `.nvmrc` 中的 `20`）。

### 一条命令启动（推荐）

```bash
cd /path/to/EasyQuant/web_strategy_studio
npm run install:all   # 首次运行：安装前后端依赖 + 构建符号表
npm run dev:all       # 启动后端 uvicorn(:8080) + 前端 Vite(:5173)
```

`dev:all` 由 `concurrently` 同时拉起两个进程，`Ctrl+C` 一次结束全部。

### 分步启动

如果只想单独启动某一端：

```bash
# 1. 安装后端
cd /path/to/EasyQuant
pip install -e .

cd web_strategy_studio/backend
pip install -e .

# 2. 启动 API（默认 127.0.0.1:8080）
python -m uvicorn studio_api.app:app --reload --host 127.0.0.1 --port 8080
```

```bash
# 3. 安装并启动前端
cd web_strategy_studio/frontend
npm install
npm run dev
```

然后在浏览器中打开 `http://localhost:5173/`。

### 环境变量

后端通过 `pydantic-settings` 读取环境变量（前缀 `EQ_STUDIO_`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EQ_STUDIO_DATABASE_URL` | SQLAlchemy 异步 DSN | `sqlite+aiosqlite:///./studio.sqlite3` |
| `EQ_STUDIO_ARTIFACT_DIR` | 报告与产物目录 | `<仓库根>/artifacts` |
| `EQ_STUDIO_REPO_ROOT` | EasyQuant 仓库根路径 | 由 `config.py` 自动推断 |
| `EQ_STUDIO_RUN_TIMEOUT_SEC` | 单任务超时（秒） | `900` |
| `EQ_STUDIO_UVICORN_PORT` | 后端监听端口 | `8080` |
| `EQ_STUDIO_MAX_CONCURRENT_RUNS` | 同时运行回测上限 | `2` |

生产环境中若前后端不在同一域名，需在前端设置：

```bash
# frontend/.env.production
VITE_API_ORIGIN=https://your-api-host
```

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| `Address already in use`（端口 8080） | `lsof -ti :8080 \| xargs kill`，或 `EQ_STUDIO_UVICORN_PORT=8081 npm run dev:all` |
| `crypto.getRandomValues is not a function` | Node 版本过低，升级到 18+ |
| 子进程引用了错误的 `studio_api` 包 | `pip uninstall eq-studio-api -y` 后在本目录重新 `pip install -e .` |
| macOS / Windows 兼容性 | macOS/Linux 直接用 `npm run dev:all`；Windows 用 WSL / Git Bash |

---

## 部署方式

### Docker Compose

在仓库根目录执行：

```bash
cd /path/to/EasyQuant
docker compose -f web_strategy_studio/docker-compose.yml build
docker compose -f web_strategy_studio/docker-compose.yml up -d
```

Compose 会同时构建两个服务：

| 服务 | 说明 |
|------|------|
| `api` | FastAPI + eqlib，监听 8080 内部端口 |
| `nginx` | 前端静态资源 + 反向代理 `/api` 和 `/static`，暴露 8080 |

数据通过 `studio-data` 持久化卷挂载，包含 SQLite 数据库和回测报告。

### 生产构建（前端静态托管）

如果你已有 Web 服务器，只需：

```bash
# 构建前端静态资源
cd web_strategy_studio/frontend
npm run build
# 产物在 frontend/dist/

# 后端单独部署（任意 WSGI/ASGI 宿主）
cd web_strategy_studio/backend
pip install -e .
uvicorn studio_api.app:app --host 0.0.0.0 --port 8080 --workers 1
```

Nginx 配置示例（前端静态资源 + `/api` 反向代理）：

```nginx
server {
    listen 80;
    server_name studio.example.com;

    # 前端 SPA
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态报告
    location /static {
        proxy_pass http://127.0.0.1:8080;
    }
}
```
