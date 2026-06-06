# Web Strategy Studio 重构 — 总执行计划

## 执行顺序

```
Phase 0: 基础搭建（1-2天）
├── 0.1 前端UI基础（主题、组件库、布局）
│   └── docs/superpowers/plans/2025-06-06-frontend-ui-refactor.md
│       ├── Task 1: 初始化前端项目
│       ├── Task 2: 设计令牌和主题系统
│       ├── Task 3: 全局布局组件
│       ├── Task 4: shadcn/ui组件库
│       └── Task 5: 重构登录页
│
Phase 1: 核心模块重构（按你的顺序）
├── 1.1 模块D — 数据管理
│   └── docs/superpowers/plans/2025-06-06-module-D-data-management.md
│
├── 1.2 模块C — 报告系统
│   └── docs/superpowers/plans/2025-06-06-module-C-report-system.md
│
├── 1.3 模块B — 回测引擎
│   └── docs/superpowers/plans/2025-06-06-module-B-backtest-engine.md
│
├── 1.4 模块A — 策略编辑器
│   └── docs/superpowers/plans/2025-06-06-module-A-strategy-editor.md
│
├── 1.5 模块E — 认证权限
│   └── docs/superpowers/plans/2025-06-06-module-E-auth-permissions.md
│
Phase 2: 稳定性提升（1-2天）
└── 2.1 Bug修复与稳定性
    └── docs/superpowers/plans/2025-06-06-final-bug-fixes.md
```

## 说明

### UI重构的位置

**UI重构在最开始（Phase 0）**，它是整个项目的前置工作：

1. **为什么UI要先做？**
   - 所有模块的前端都依赖统一的设计系统
   - 主题、组件库、布局是基础设施
   - 先建好UI基础，后续模块重构时可以直接使用

2. **UI重构与模块重构的关系**
   - Phase 0: 搭建UI框架（主题、组件、布局）
   - Phase 1: 每个模块重构时，前端直接使用新UI组件
   - Phase 2: 最终统一优化和修复

### 执行策略

```
Week 1:
  Day 1-2: Phase 0 — UI基础搭建
  Day 3-5: Phase 1 — 模块D + 模块C

Week 2:
  Day 1-3: Phase 1 — 模块B + 模块A
  Day 4-5: Phase 1 — 模块E

Week 3:
  Day 1-3: Phase 2 — Bug修复 + 稳定性
  Day 4-5: 测试完善 + 性能优化
```

### 每个模块的执行方式

每个模块都有独立的实施计划，包含：
- 详细的任务分解
- 具体的代码实现
- 完整的测试用例
- Git提交流程

你可以按顺序逐个执行，也可以并行推进（如果有多个开发者）。
