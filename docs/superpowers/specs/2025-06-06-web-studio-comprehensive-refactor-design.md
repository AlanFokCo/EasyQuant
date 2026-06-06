# Web Strategy Studio — 全面重构升级设计规格

## 1. 概述与目标

### 1.1 项目背景

Web Strategy Studio 是 EasyQuant 的浏览器端策略开发与回测平台，允许用户在浏览器中编辑 Python 策略、运行回测、查看报告。当前版本基于 FastAPI + React 18 + Vite，已具备基础功能但存在安全漏洞、性能瓶颈、Bug 和测试覆盖不足等问题。

### 1.2 设计目标

- **体验专业**：现代化的 UI/UX，流畅的交互，符合专业量化平台的审美标准
- **系统稳定**：零已知 Bug，健壮的异常处理，完善的资源清理机制
- **性能优秀**：异步 I/O，合理的缓存策略，快速的页面响应
- **安全坚固**：完整的安全防护，严格的输入校验，最小权限原则
- **可测试性**：80%+ 测试覆盖率，CI/CD 集成

### 1.3 设计原则

1. **安全优先**：所有设计决策首先考虑安全性
2. **性能优先**：关键路径响应 < 200ms，回测启动 < 3s
3. **类型安全**：前后端共享 Schema，编译期类型检查
4. **渐进增强**：核心功能优先，逐步添加增强功能
5. **向后兼容**：关键 API 保持向后兼容，平滑迁移

## 2. 技术架构

### 2.1 前端技术栈

| 技术 | 版本 | 用途 | 选择理由 |
|------|------|------|----------|
| React | 19.x | UI 框架 | 最新稳定版，并发特性，性能优化 |
| TypeScript | 5.6+ | 类型系统 | 编译期类型检查，IDE 智能提示 |
| Vite | 6.x | 构建工具 | 极速冷启动，优秀的开发体验 |
| shadcn/ui | 最新 | 组件库 | 基于 Radix UI，高度可定制，暗/亮主题原生支持 |
| Tailwind CSS | 4.x | CSS 框架 | 原子化 CSS，构建产物小，开发效率高 |
| Zustand | 4.x | 状态管理 | 轻量，TypeScript 原生支持，保留现有方案 |
| TanStack Query | 5.x | 服务端状态 | 缓存、重试、轮询，保留现有方案 |
| React Hook Form | 7.x | 表单处理 | 性能优秀，与 Zod 集成好 |
| Zod | 3.x | 数据校验 | TypeScript 原生，前后端共享 |
| Framer Motion | 11.x | 动画效果 | 流畅的过渡动画，提升体验 |
| Monaco Editor | 0.47+ | 代码编辑器 | 保留现有方案，增强集成 |
| lightweight-charts | 4.x | 图表展示 | 专业级金融图表，性能优秀 |

### 2.2 后端技术栈

| 技术 | 版本 | 用途 | 选择理由 |
|------|------|------|----------|
| FastAPI | 0.115+ | Web 框架 | 保留现有方案，升级最新稳定版 |
| SQLAlchemy | 2.x | ORM | 保留现有方案，async 原生支持 |
| Pydantic | 2.x | 数据校验 | 与 FastAPI 深度集成 |
| structlog | 24.x | 结构化日志 | 保留现有方案 |
| python-jose | 3.x | JWT 处理 | 安全 token 签发/验证 |
| passlib | 1.7+ | 密码哈希 | bcrypt 算法，安全哈希 |
| pytest | 8.x | 测试框架 | 保留现有方案 |
| pytest-asyncio | 0.24+ | async 测试 | 支持 async/await 测试 |
| httpx | 0.28+ | HTTP 客户端 | async 支持，测试用 TestClient |
| aiosqlite | 0.20+ | SQLite async | SQLAlchemy async 适配 |
| asyncpg | 0.29+ | PostgreSQL async | 生产环境高性能连接 |

### 2.3 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (React 19 + Vite)              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ 策略编辑器    │  │ 回测执行     │  │ 报告查看/对比       │ │
│  │ Monaco + 工具 │  │ SSE 进度流   │  │ lightweight-charts  │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ 数据管理      │  │ 用户认证     │  │ 系统设置/管理       │ │
│  │ 批量操作     │  │ JWT + RBAC   │  │ 配置/日志/监控       │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API 网关层 (FastAPI)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ /api/v1/auth  │  │ /api/v1/runs │  │ /api/v1/strategies │ │
│  │ JWT 验证     │  │ SSE 流       │  │ CRUD + 版本控制     │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ /api/v1/data │  │ /api/v1/lint │  │ /api/v1/reports    │ │
│  │ 异步 I/O     │  │ 代码检查     │  │ 静态报告服务       │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐   ┌─────────┐   ┌─────────────┐
        │ SQLite  │   │ Redis   │   │ 文件系统     │
        │(默认)   │   │(可选)   │   │ 报告/产物   │
        └─────────┘   └─────────┘   └─────────────┘
```

## 3. 模块详细设计

### 3.1 模块 A：策略编辑器

#### 3.1.1 功能需求

1. **代码编辑**
   - Monaco Editor 集成，支持 Python 语法高亮
   - eqlib API 自动补全（基于 eqlib_symbols.json）
   - 实时语法检查（Ruff）
   - 代码格式化（Black）
   - 行号显示、代码折叠、查找替换

2. **版本管理**
   - 自动保存（debounce 3s）
   - 手动保存触发版本快照
   - 版本历史列表（时间、作者、变更摘要）
   - 版本对比（diff view）
   - 版本回滚

3. **策略模板**
   - 内置常用模板（双均线、动量、均值回归等）
   - 模板预览（代码 + 说明）
   - 从模板创建策略

4. **辅助工具**
   - 代码片段（Snippets）
   - 快捷键参考（Cheatsheet）
   - 股票选择器（内嵌）

#### 3.1.2 界面设计

```
┌──────────────────────────────────────────────────────────────┐
│ [保存] [运行] [格式化] [模板▼] [股票▼] [版本▼]               │  ← 工具栏
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  def initialize(ctx):                                        │
│      ctx.assigner = ctx.target(["600519"])                   │
│                                                              │
│  def handle_bar(ctx):                                       │
│      # 双均线策略                                           │
│      for stock in ctx.target_list:                          │
│          hist = ctx.data.history(stock, 30)                 │
│          if len(hist) < 30:                                 │
│              continue                                       │
│          ma5 = hist[-5:].mean()                             │
│          ma20 = hist[-20:].mean()                           │
│          if ma5 > ma20:                                     │
│              ctx.order_target_percent(stock, 0.5)           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ 状态: 已保存 | 版本: v3 | 最后修改: 2025-06-06 14:30:00    │  ← 状态栏
└──────────────────────────────────────────────────────────────┘
```

#### 3.1.3 API 设计

```python
# GET /api/v1/strategies/{id}/versions — 获取版本列表
# POST /api/v1/strategies/{id}/versions — 创建新版本快照
# GET /api/v1/strategies/{id}/versions/{version_id} — 获取特定版本
# POST /api/v1/strategies/{id}/versions/{version_id}/restore — 回滚到版本
# POST /api/v1/strategies/{id}/lint — 运行静态检查
# POST /api/v1/strategies/{id}/format — 运行代码格式化
# GET /api/v1/templates — 获取策略模板列表
# GET /api/v1/templates/{template_id} — 获取模板详情
```

#### 3.1.4 组件设计

```typescript
// StrategyEditor.tsx — 主组件
interface StrategyEditorProps {
  strategyId: string;
  onSave: (code: string) => Promise<void>;
  onRun: () => void;
}

// VersionHistory.tsx — 版本历史面板
interface VersionHistoryProps {
  strategyId: string;
  onSelect: (version: Version) => void;
  onCompare: (v1: Version, v2: Version) => void;
}

// TemplateSelector.tsx — 模板选择器
interface TemplateSelectorProps {
  onSelect: (template: Template) => void;
}

// CodeQualityIndicator.tsx — 代码质量指示器
interface CodeQualityIndicatorProps {
  lintResults: LintResult[];
}
```

### 3.2 模块 B：回测执行引擎

#### 3.2.1 功能需求

1. **回测配置**
   - 策略选择
   - 回测时间范围
   - 初始资金
   - 手续费率
   - 参数调优（网格搜索）

2. **执行管理**
   - 异步提交回测任务
   - 实时进度追踪（SSE）
   - 日志流实时查看
   - 任务取消（安全中断）
   - 并发控制（最大并行数）

3. **执行模式**
   - 本地执行（子进程）
   - Docker 执行（沙箱隔离）

#### 3.2.2 SSE 协议设计

```
Event: log
Data: {"level": "info", "message": "开始回测...", "timestamp": "2025-06-06T14:30:00Z"}

Event: progress
Data: {"percent": 45, "current": "2023-06-15", "elapsed": 120, "estimated": 180}

Event: done
Data: {"status": "success", "report_url": "/api/v1/reports/{run_id}/report.html", "metrics": {...}}

Event: error
Data: {"error": "ZeroDivisionError", "traceback": "...", "message": "除零错误"}
```

#### 3.2.3 API 设计

```python
# POST /api/v1/runs — 提交回测任务
# GET /api/v1/runs/{id} — 获取任务状态
# POST /api/v1/runs/{id}/cancel — 取消任务
# GET /api/v1/runs/{id}/stream — SSE 事件流
# GET /api/v1/runs — 获取任务列表（分页）
# DELETE /api/v1/runs/{id} — 删除任务及产物
```

#### 3.2.4 安全设计

- 所有运行端点要求认证
- 输入参数严格校验（时间范围、资金、手续费）
- 代码执行沙箱（AST 黑名单 + Docker 隔离）
- 超时控制（默认 900s）
- 内存限制（默认 2048MB）

### 3.3 模块 C：报告系统

#### 3.3.1 功能需求

1. **报告查看**
   - HTML 报告嵌入预览
   - 关键指标卡片展示
   - 收益曲线图（lightweight-charts）
   - 交易记录表格
   - 风险指标展示

2. **报告对比**
   - 选择多个报告对比
   - 收益曲线叠加
   - 指标并排对比
   - 差异高亮

3. **报告导出**
   - HTML 下载
   - PDF 导出
   - PNG 截图
   - JSON 原始数据

#### 3.3.2 界面设计

```
┌──────────────────────────────────────────────────────────────┐
│ 报告查看                                                     │
├──────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│ │ 总收益率    │ │ 年化收益    │ │ 最大回撤    │           │
│ │ 15.23%     │ │ 8.45%      │ │ -3.21%     │           │
│ └─────────────┘ └─────────────┘ └─────────────┘           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 收益曲线（lightweight-charts）                           │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 交易记录（表格，支持分页、排序、筛选）                      │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

#### 3.3.3 API 设计

```python
# GET /api/v1/reports/{run_id}/report.html — HTML 报告
# GET /api/v1/reports/{run_id}/metrics — 指标数据
# GET /api/v1/reports/{run_id}/trades — 交易记录
# POST /api/v1/reports/compare — 报告对比
# GET /api/v1/reports/{run_id}/export/{format} — 报告导出
```

### 3.4 模块 D：数据管理

#### 3.4.1 功能需求

1. **数据浏览**
   - 本地数据列表（分页、搜索、筛选）
   - 数据基本信息（代码、名称、日期范围、文件大小）
   - 数据预览（最近 N 条记录）

2. **数据操作**
   - 批量下载
   - 批量删除
   - 数据导入（CSV/Excel）
   - 数据更新（增量更新）

3. **数据质量**
   - 缺失值检测
   - 异常值检测
   - 数据完整性报告

#### 3.4.2 性能优化

- 异步 I/O（aiofiles）
- 数据库查询分页（limit/offset）
- 缓存热点数据（Redis/TTLDict）
- 批量操作减少往返

#### 3.4.3 API 设计

```python
# GET /api/v1/data/stocks — 股票列表（分页）
# GET /api/v1/data/stocks/{code} — 股票详情
# GET /api/v1/data/stocks/{code}/preview — 数据预览
# POST /api/v1/data/stocks/{code}/download — 下载数据
# DELETE /api/v1/data/stocks — 批量删除
# POST /api/v1/data/stocks/import — 导入数据
# GET /api/v1/data/stocks/{code}/quality — 数据质量报告
```

### 3.5 模块 E：认证与权限

#### 3.5.1 功能需求

1. **认证**
   - 用户名/密码登录
   - JWT Token（access + refresh）
   - Token 自动刷新
   - 多设备登录管理

2. **注册控制**
   - 管理员开关（允许/禁止注册）
   - 邀请码机制（可选）
   - 邮箱验证（可选）

3. **权限管理**
   - 角色定义（admin, user, guest）
   - 资源级别权限（读/写/执行/删除）
   - API 端点级别权限控制

4. **安全特性**
   - 密码强度验证（最小 8 位，含大小写、数字、特殊字符）
   - 登录失败锁定（5 次失败后锁定 15 分钟）
   - 会话超时（默认 30 天）
   - 强制密码更新（可选）

#### 3.5.2 JWT 设计

```python
# Access Token
{
    "sub": "user_id",
    "username": "alice",
    "role": "user",
    "iat": 1717683600,
    "exp": 1717687200,  # 1 hour
    "jti": "unique-token-id"
}

# Refresh Token
{
    "sub": "user_id",
    "type": "refresh",
    "exp": 1720265600,  # 30 days
    "jti": "unique-refresh-id"
}
```

#### 3.5.3 API 设计

```python
# POST /api/v1/auth/login — 登录
# POST /api/v1/auth/register — 注册（可选关闭）
# POST /api/v1/auth/refresh — 刷新 Token
# POST /api/v1/auth/logout — 登出
# GET /api/v1/auth/me — 获取当前用户信息
# PUT /api/v1/auth/me — 更新用户信息
# POST /api/v1/auth/change-password — 修改密码
```

## 4. 数据库设计

### 4.1 实体关系

```
User (1) ───< (N) Strategy
User (1) ───< (N) Run
User (1) ───< (N) Session

Strategy (1) ───< (N) StrategyVersion
Strategy (1) ───< (N) Run

Run (1) ───< (1) Report
```

### 4.2 表结构

```sql
-- users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user', -- admin, user, guest
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- strategies
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    template_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- strategy_versions
CREATE TABLE strategy_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    version_number INTEGER NOT NULL,
    code TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy_id, version_number)
);

-- runs
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, success, failed, cancelled
    params TEXT NOT NULL, -- JSON
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT,
    html_path TEXT,
    json_path TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- sessions
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token_jti TEXT NOT NULL,
    user_agent TEXT,
    ip_address TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 5. 安全设计

### 5.1 认证安全

- **JWT Secret**：从环境变量读取，不存在时生成并持久化到文件
- **Token 存储**：Access Token 在内存，Refresh Token 在 httpOnly cookie
- **Token 轮换**：每次刷新时生成新的 access + refresh token，旧 token 加入黑名单

### 5.2 输入安全

- **SQL 注入**：使用 SQLAlchemy ORM，参数化查询
- **XSS**：所有输出 HTML escape，富文本使用 DOMPurify
- **CSRF**：SameSite cookie + CSRF Token（可选）
- **路径遍历**：路径参数白名单校验，使用 `safe_join`

### 5.3 执行安全

- **代码沙箱**：AST 黑名单扫描 + Docker 隔离
- **资源限制**：CPU、内存、时间、网络限制
- **文件系统隔离**：每个任务独立工作目录

### 5.4 速率限制

- **认证端点**：5 次/分钟
- **回测提交**：10 次/小时
- **通用 API**：1000 次/小时
- **实现**：Redis 计数器（生产）/ 内存计数器（开发）

## 6. 性能设计

### 6.1 前端性能

- **代码分割**：路由级别懒加载
- **资源优化**：图片 WebP、字体子集化、CSS 提取
- **状态优化**：React.memo、useMemo、useCallback 合理使用
- **虚拟滚动**：大数据列表使用 react-window/react-virtuoso

### 6.2 后端性能

- **异步 I/O**：所有阻塞操作异步化
- **数据库优化**：索引、分页、N+1 查询消除
- **缓存策略**：热点数据 Redis 缓存，TTL 过期
- **连接池**：数据库连接池、HTTP 连接池

### 6.3 目标指标

| 指标 | 目标 |
|------|------|
| 首屏加载时间 | < 2s |
| API 响应时间 (P95) | < 200ms |
| 回测启动时间 | < 3s |
| SSE 延迟 | < 100ms |
| 并发回测数 | >= 4 |

## 7. 测试策略

### 7.1 测试金字塔

```
     ┌─────────┐
     │  E2E   │  — 关键用户旅程（< 10%）
    ┌─────────┐
    │Integration│ — API 集成（20%）
   ┌─────────┐
   │  Unit   │  — 业务逻辑（70%）
   └─────────┘
```

### 7.2 测试覆盖目标

- **后端**：80%+ 行覆盖率
- **前端**：70%+ 行覆盖率
- **E2E**：关键路径全覆盖

### 7.3 测试类型

1. **单元测试**
   - 工具函数、Hook、组件
   - 使用 Jest + React Testing Library（前端）
   - 使用 pytest + pytest-asyncio（后端）

2. **集成测试**
   - API 端点测试（TestClient）
   - 数据库操作测试
   - SSE 流测试

3. **E2E 测试**
   - 完整用户旅程
   - 使用 Playwright

### 7.4 关键测试场景

- 用户注册 → 登录 → 创建策略 → 编辑代码 → 运行回测 → 查看报告
- 并发回测（资源竞争）
- 网络中断恢复（SSE 重连）
- 大数据量处理（1000+ 股票）
- 安全测试（SQL 注入、XSS、路径遍历）

## 8. 部署与运维

### 8.1 部署架构

```
┌─────────────┐
│   Nginx    │  — 反向代理、SSL 终止、静态文件
└──────┬──────┘
       │
┌──────┴──────┐
│   FastAPI   │  — API 服务（多 worker）
└──────┬──────┘
       │
┌──────┴──────┐
│  PostgreSQL │  — 数据持久化
└─────────────┘
```

### 8.2 Docker Compose

```yaml
version: "3.8"
services:
  web:
    build: .
    ports:
      - "80:80"
    environment:
      - EQ_STUDIO_DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/studio
      - EQ_JWT_SECRET=${JWT_SECRET}
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
```

### 8.3 监控

- **日志**：结构化 JSON 日志，ELK/Loki 收集
- **指标**：Prometheus + Grafana
- **告警**：关键错误率、响应时间、资源使用率

## 9. 迁移计划

### 9.1 阶段划分

| 阶段 | 时间 | 目标 |
|------|------|------|
| Phase 1 | Week 1 | 后端安全修复 + 基础架构升级 |
| Phase 2 | Week 2 | 前端框架升级 + 基础组件库搭建 |
| Phase 3 | Week 3-4 | 模块 A/B 重构 |
| Phase 4 | Week 5-6 | 模块 C/D/E 重构 |
| Phase 5 | Week 7 | Bug 修复 + 稳定性优化 |
| Phase 6 | Week 8 | 测试完善 + 性能优化 |

### 9.2 向后兼容

- 数据库：Alembic 迁移脚本，支持回滚
- API：v1 端点保持，v2 逐步引入
- 前端：功能开关，灰度发布

## 10. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重构引入新 Bug | 高 | 完整测试覆盖，逐步发布 |
| 性能不达标 | 中 | 性能测试，缓存优化 |
| 安全漏洞 | 高 | 安全审计，渗透测试 |
| 进度延迟 | 中 | 分阶段交付，优先级管理 |

## 11. 结论

本设计规格为 Web Strategy Studio 的全面重构提供了详细的架构设计、模块划分、安全策略和测试方案。通过系统性的重构，我们将打造一个**体验专业、系统稳定、安全坚固**的量化策略开发平台。

---

## 12. 前端 UI/UX 全面重新设计

### 12.1 设计哲学

Web Strategy Studio 的 UI 设计参考了 Bloomberg Terminal、TradingView、QuantConnect 等专业级量化平台的最佳实践，同时兼顾开发者的使用习惯，打造"专业但不复杂，强大但友好"的界面。

**核心理念**：
- **专业感**：深色主题为主，专业配色，金融级数据展示
- **沉浸感**：最小化干扰，最大化代码和数据展示空间
- **效率优先**：常用操作快捷键化，减少鼠标移动距离
- **一致性**：所有交互模式统一，降低学习成本
- **反馈及时**：每个操作都有明确的视觉反馈

### 12.2 色彩系统

#### 12.2.1 暗色主题（默认）

```
Primary Colors:
- background:      #0f1115  (主背景)
- surface:         #181a20  (卡片/面板背景)
- surface-raised:  #1e2028  (悬浮面板)
- border:          #2a2d35  (边框)

Accent Colors:
- primary:         #3b82f6  (主要操作/链接)
- primary-hover:   #2563eb  (主要操作悬停)
- success:         #22c55e  (成功/收益)
- warning:         #eab308  (警告)
- danger:          #ef4444  (错误/亏损)
- info:            #06b6d4  (信息)

Text Colors:
- text-primary:    #f1f5f9  (主文本)
- text-secondary:  #94a3b8  (次要文本)
- text-muted:      #64748b  (辅助文本)
- text-inverse:    #0f1115  (反色文本)

Chart Colors:
- chart-line:      #3b82f6  (主线)
- chart-area:      rgba(59, 130, 246, 0.1)  (面积)
- chart-grid:      #2a2d35  (网格)
- chart-crosshair: #94a3b8  (十字线)
```

#### 12.2.2 亮色主题

```
Primary Colors:
- background:      #ffffff
- surface:         #f8fafc
- surface-raised:  #f1f5f9
- border:          #e2e8f0

Accent Colors:
- primary:         #2563eb
- primary-hover:   #1d4ed8
- success:         #16a34a
- warning:         #ca8a04
- danger:          #dc2626
- info:            #0891b2

Text Colors:
- text-primary:    #0f172a
- text-secondary:  #475569
- text-muted:      #64748b
- text-inverse:    #ffffff
```

### 12.3 字体系统

```
Font Family:
- Sans-serif: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto
- Monospace:  JetBrains Mono, "Fira Code", "SF Mono", Consolas, monospace
- Display:    Inter (weight 600+)

Font Sizes:
- display:    2rem    (32px)  — 页面标题
- heading-1:  1.5rem  (24px)  — 模块标题
- heading-2:  1.25rem (20px)  — 卡片标题
- heading-3:  1rem    (16px)  — 小节标题
- body:       0.875rem (14px) — 正文
- body-sm:    0.75rem  (12px) — 辅助文本
- caption:    0.6875rem (11px) — 标签/图例

Line Height:
- tight:  1.25  — 标题
- normal: 1.5   — 正文
- relaxed: 1.75 — 大段文本

Font Weight:
- normal:  400
- medium:  500
- semibold: 600
- bold:    700
```

### 12.4 间距系统

基于 4px 的间距单位：

```
space-0.5:  2px
space-1:    4px
space-2:    8px
space-3:   12px
space-4:   16px
space-5:   20px
space-6:   24px
space-8:   32px
space-10:  40px
space-12:  48px
space-16:  64px
```

### 12.5 布局架构

#### 12.5.1 全局布局

```
┌──────────────────────────────────────────────────────────────┐
│ [Logo]  EasyQuant Studio              [通知] [设置] [用户▼] │  Header (48px)
├──────┬───────────────────────────────────────────────────────┤
│      │                                                       │
│  ┌───┤                                                       │
│  │   │                    Main Content Area                  │
│  │ N │                                                       │
│  │ a │   ┌──────────────┐  ┌──────────────┐                 │
│  │ v │   │              │  │              │                 │
│  │ i │   │   Panel 1    │  │   Panel 2    │                 │
│  │ g │   │              │  │              │                 │
│  │ a │   │              │  │              │                 │
│  │ t │   └──────────────┘  └──────────────┘                 │
│  │ i │                                                       │
│  │ o │   ┌────────────────────────────────────┐           │
│  │ n │   │              Panel 3               │           │
│  │   │   │                                  │           │
│  │   │   └────────────────────────────────────┘           │
│  └───┘                                                       │
│       Sidebar (64px collapsed / 240px expanded)              │
│                                                              │
├──────┴───────────────────────────────────────────────────────┤
│ Status: Connected | 4 runs active | Memory: 45%             │  Status Bar (28px)
└──────────────────────────────────────────────────────────────┘
```

#### 12.5.2 布局模式

**模式 1：开发者模式（默认）**
```
┌────────────────────────────────────────────────────────┐
│ [Sidebar] │ [代码编辑器 60%] │ [运行面板 40%]          │
│           │                   │ [日志] [进度] [结果]     │
└────────────────────────────────────────────────────────┘
```

**模式 2：分析师模式**
```
┌────────────────────────────────────────────────────────┐
│ [Sidebar] │ [报告查看器 100%]                          │
│           │ [指标卡] [收益曲线] [交易记录] [分析]      │
└────────────────────────────────────────────────────────┘
```

**模式 3：全屏模式**
```
┌────────────────────────────────────────────────────────┐
│ [代码编辑器全屏]                                        │
│ 或 [报告全屏]                                          │
└────────────────────────────────────────────────────────┘
```

### 12.6 页面详细设计

#### 12.6.1 登录页

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│                    ┌─────────────┐                     │
│                    │             │                     │
│                    │   Logo      │                     │
│                    │   128x128   │                     │
│                    │             │                     │
│                    └─────────────┘                     │
│                                                        │
│              EasyQuant Strategy Studio                 │
│              专业的量化策略开发平台                     │
│                                                        │
│              ┌─────────────────────┐                   │
│              │ 用户名             │                    │
│              └─────────────────────┘                   │
│              ┌─────────────────────┐                   │
│              │ 密码               │ [显示/隐藏]        │
│              └─────────────────────┘                   │
│                                                        │
│              ┌─────────────────────┐                   │
│              │     登 录          │                    │
│              └─────────────────────┘                   │
│                                                        │
│              忘记密码？  |  没有账号？联系管理员          │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**设计要点**：
- 深色背景 + 渐变光效，营造专业氛围
- 居中单卡片布局，聚焦登录操作
- 输入框聚焦时边框高亮动画
- 登录按钮 hover 时微缩放效果
- 错误提示以 toast 形式出现，不破坏布局

#### 12.6.2 策略编辑页（核心页面）

```
┌────────────────────────────────────────────────────────────────┐
│ Header                                                         │
├────────────┬───────────────────────────────────────────────────┤
│            │ Toolbar: [保存 ⌘S] [运行 ⌘R] [格式化 ⌘Shift+F]    │
│ Sidebar    │       [模板▼] [股票▼] [版本▼] [更多▼]           │
│            ├───────────────────────────────────────────────────┤
│ [策略列表] │                                                   │
│   - 双均线 │  ┌─────────────────────────────────────────────┐ │
│   - 动量   │  │ def initialize(ctx):                         │ │
│   - 均值   │  │     ctx.assigner = ctx.target(["600519"])   │ │
│            │  │                                               │ │
│ [新建]     │  │ def handle_bar(ctx):                         │ │
│            │  │     for stock in ctx.target_list:            │ │
│ [数据]     │  │         hist = ctx.data.history(stock, 30)  │ │
│ [回测]     │  │         ...                                   │ │
│ [报告]     │  └─────────────────────────────────────────────┘ │
│            │                                                   │
│ [设置]     │  ┌──────────────┐  ┌──────────────┐            │
│            │  │ 运行日志      │  │ 运行进度      │            │
│            │  │ [========]   │  │ 45%          │            │
│            │  └──────────────┘  └──────────────┘            │
│            │                                                   │
│            │  ┌───────────────────────────────────────────┐   │
│            │  │ 回测结果预览                               │   │
│            │  │ 总收益: 15.23%  |  夏普: 1.45            │   │
│            │  └───────────────────────────────────────────┘   │
│            │                                                   │
├────────────┴───────────────────────────────────────────────────┤
│ Status Bar: 已保存 | 版本: v3 | 行: 45, 列: 12              │
└────────────────────────────────────────────────────────────────┘
```

**设计要点**：
- **三栏布局**：左侧导航（可折叠）、中间代码编辑（核心区域）、右侧运行面板
- **代码区域**：Monaco Editor，深色主题，eqlib 语法高亮
- **运行面板**：可折叠标签页（日志/进度/结果）
- **状态栏**：底部固定，显示关键信息
- **自动保存**：3s debounce，保存时有微光效提示

#### 12.6.3 报告查看页

```
┌──────────────────────────────────────────────────────────────┐
│ Header: [返回] 策略名称 — 回测报告 2025-06-06 14:30:00      │
├──────────────────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│ │ 总收益率   │ │ 年化收益   │ │ 最大回撤   │ │ 夏普比率   │   │
│ │ +15.23%   │ │ +8.45%    │ │ -3.21%    │ │ 1.45      │   │
│ │ ↑ 3.2%    │ │ vs 基准   │ │ ↑ 0.5%    │ │ ↑ 0.3     │   │
│ └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ 收益曲线（lightweight-charts）                          │  │
│ │                                                        │  │
│ │                                                        │  │
│ └────────────────────────────────────────────────────────┘  │
│ ┌─────────────────────┐  ┌─────────────────────────────┐   │
│ │ 月度收益热力图       │  │ 资产分布饼图                  │   │
│ │ [热力图占位]        │  │ [饼图占位]                    │   │
│ └─────────────────────┘  └─────────────────────────────┘   │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ 交易记录（表格，支持排序、筛选、分页）                   │  │
│ │                                                       │  │
│ └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**设计要点**：
- 指标卡片：大号数字 + 趋势箭头 + 对比基准
- 图表：专业金融图表风格，深色背景，网格线
- 表格：斑马纹 + 悬停高亮 + 排序图标
- 响应式：移动端卡片堆叠，图表自适应

#### 12.6.4 数据管理页

```
┌──────────────────────────────────────────────────────────────┐
│ Header: 数据管理                                [上传] [刷新] │
├──────────────────────────────────────────────────────────────┤
│ 筛选: [全部▼] [日期范围] [搜索: _______]          [批量操作▼] │
├──────────────────────────────────────────────────────────────┤
│ ┌──────┬─────────┬────────────┬──────────┬──────────┬─────┐│
│ │ 选择 │ 代码    │ 名称      │ 日期范围  │ 大小    │ 操作││
│ ├──────┼─────────┼────────────┼──────────┼──────────┼─────┤│
│ │ [✓]  │ 600519  │ 贵州茅台  │ 2020-2025│ 12.5 MB │ […]││
│ │ [✓]  │ 000001  │ 平安银行  │ 2020-2025│ 11.2 MB │ […]││
│ │ [ ]  │ 002594  │ 比亚迪    │ 2020-2025│ 10.8 MB │ […]││
│ └──────┴─────────┴────────────┴──────────┴──────────┴─────┘│
│ 共 3 条数据，已选择 2 条                                   │
└──────────────────────────────────────────────────────────────┘
```

### 12.7 组件设计规范

#### 12.7.1 按钮

```
Variants:
- primary:   bg-primary text-white hover:bg-primary-hover
- secondary: bg-surface border border-border hover:bg-surface-raised
- ghost:     bg-transparent hover:bg-surface-raised
- danger:    bg-danger text-white hover:bg-danger-hover

Sizes:
- sm:  h-8 px-3 text-sm
- md:  h-10 px-4 text-sm
- lg:  h-12 px-6 text-base

States:
- default → hover (bg 变深) → active (scale 0.98) → disabled (opacity 50%)
- loading: spinner + disabled
```

#### 12.7.2 输入框

```
Base:    bg-surface border border-border rounded-md px-3 py-2
Focus:   border-primary ring-2 ring-primary/20
Error:   border-danger ring-2 ring-danger/20 + 下方红色错误文本
Success: border-success + 右侧 ✓ 图标
Disabled: bg-muted/50 opacity-50
```

#### 12.7.3 卡片

```
Base:     bg-surface border border-border rounded-lg shadow-sm
Hover:    shadow-md border-border/80
Selected: ring-2 ring-primary

Variants:
- default:  padding 24px
- compact:  padding 16px
- flat:     no shadow, no border
```

#### 12.7.4 表格

```
Header:   bg-surface-raised font-semibold text-sm
Row:      border-b border-border hover:bg-surface-raised/50
Selected: bg-primary/5
Sorted:   列头显示 ↑ ↓ 图标
Empty:    居中显示 "暂无数据" + 图标
Loading:  Skeleton 骨架屏
```

#### 12.7.5 模态框

```
Overlay:  bg-black/50 backdrop-blur-sm
Panel:    bg-surface rounded-xl shadow-xl max-w-lg mx-auto
Header:   px-6 py-4 border-b border-border
Body:     px-6 py-4
Footer:   px-6 py-4 border-t border-border flex justify-end gap-3
Animation: fade-in + scale-in (200ms, ease-out)
Close:    ESC 键 / 点击遮罩 / × 按钮
```

#### 12.7.6 Toast 通知

```
Position: bottom-right (desktop), top-center (mobile)
Variants: success (green), error (red), warning (yellow), info (blue)
Duration: 3s (auto-dismiss), 5s (error)
Animation: slide-in-right, fade-out
Max: 5 个同时显示
```

### 12.8 交互与动效

#### 12.8.1 页面过渡

```
Initial:  opacity 0, translateY(10px)
Animate:  opacity 1, translateY(0)
Duration: 200ms
Easing:   ease-out
```

#### 12.8.2 模态框动画

```
Overlay:  opacity 0 → 1 (150ms)
Panel:    scale 0.95, opacity 0 → scale 1, opacity 1 (200ms)
Easing:   cubic-bezier(0.16, 1, 0.3, 1)
```

#### 12.8.3 加载状态

```
Button:   spinner 替换文字，禁用点击
Card:     skeleton 骨架屏（动画渐变）
Table:    行 skeleton 占位
Page:     全屏 spinner 或 progress bar
```

#### 12.8.4 拖拽交互

```
Drag Start:  scale 1.02, shadow-lg, cursor grabbing
Drag Over:   border-dashed border-primary
Drop:        scale 1 → bounce effect
```

### 12.9 快捷键系统

| 快捷键 | 功能 | 场景 |
|--------|------|------|
| ⌘S / Ctrl+S | 保存策略 | 编辑器 |
| ⌘R / Ctrl+R | 运行回测 | 编辑器 |
| ⌘Shift+F / Ctrl+Shift+F | 格式化代码 | 编辑器 |
| ⌘F / Ctrl+F | 查找 | 编辑器 |
| ⌘Shift+P / Ctrl+Shift+P | 命令面板 | 全局 |
| ⌘K / Ctrl+K | 快速导航 | 全局 |
| Escape | 关闭模态框/面板 | 全局 |
| F11 | 全屏模式 | 编辑器 |

### 12.10 响应式设计

#### 12.10.1 断点系统

```
sm:  640px   — 手机横屏
md:  768px   — 平板
lg:  1024px  — 小型桌面
xl:  1280px  — 标准桌面
2xl: 1536px  — 大型桌面
```

#### 12.10.2 布局适配

**桌面端 (>= 1024px)**：
- 三栏布局（侧边栏 + 代码 + 面板）
- 完整的快捷键支持
- 浮动工具栏

**平板端 (768px - 1023px)**：
- 侧边栏可折叠为图标模式
- 代码和面板上下堆叠或左右分屏
- 触摸友好的按钮尺寸

**移动端 (< 768px)**：
- 侧边栏变为底部导航栏
- 单栏布局
- 代码编辑器全屏模式
- 面板变为底部抽屉
- 简化操作（长按代替右键）

### 12.11 无障碍设计 (A11y)

1. **键盘导航**：
   - 所有交互元素可通过键盘访问
   - Tab 顺序合理
   - Enter/Space 激活按钮
   - Escape 关闭弹窗

2. **屏幕阅读器**：
   - 语义化 HTML（header, nav, main, aside, footer）
   - ARIA 标签（aria-label, aria-describedby, aria-live）
   - 图标按钮有 aria-label

3. **颜色对比度**：
   - 文本与背景对比度 >= 4.5:1（WCAG AA）
   - 大文本对比度 >= 3:1
   - 不仅靠颜色传达信息（+ 图标/文字）

4. **焦点管理**：
   - 明显的焦点样式（outline 或 ring）
   - 模态框打开时焦点 trapped
   - 关闭后焦点回到触发元素

5. **动画**：
   - 支持 prefers-reduced-motion
   - 重要信息不依赖动画传达

---

**版本**: v1.1  
**日期**: 2025-06-06  
**作者**: Claude (AI Assistant)  
**状态**: 草案，待审批

