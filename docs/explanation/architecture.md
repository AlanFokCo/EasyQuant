# 系统架构

EasyQuant 由核心库 `eqlib` 和 Web 策略工作室两部分组成。本文解释它们之间的关系以及各模块的职责。

---

## 整体架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                        用户层                                    │
│  Python 脚本 / Jupyter Notebook / Web 策略工作室                  │
└─────────────┬───────────────────────────┬───────────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────────────┐
│  策略 API                │  │  Web Studio                      │
│  initialize(context)     │  │  FastAPI Backend (studio_api/)   │
│  handle_data(ctx, data)  │  │  ┌───────────────────────────┐  │
│  run_daily(func)         │  │  │ isolated_runner.py         │  │
│  order*()                │  │  │ (子进程运行回测，隔离策略代码) │  │
└─────────────┬───────────┘  │  └───────────┬───────────────┘  │
              │               │              │                   │
              ▼               └──────────────┼───────────────────┘
┌─────────────────────────────────────────────┼───────────────────┐
│  回测引擎 (eqlib/engine.py)                  │                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │                   │
│  │ 调度器    │  │ 订单撮合  │  │ 组合管理  │  │                   │
│  │run_daily  │  │ T+1 检查  │  │ 持仓/现金 │  │                   │
│  │run_weekly │  │ 100股取整  │  │ 手续费    │  │                   │
│  └──────────┘  └──────────┘  └──────────┘  │                   │
└─────────────┬───────────────┬───────────────┘                   │
              │               │                                    │
              ▼               ▼                                    │
┌──────────────────┐ ┌─────────────────────────────────────────────┤
│  数据层           │ │  分析与报告层                                │
│  eqlib/data.py   │ │  eqlib/attribution.py  (Brinson/因子分析)   │
│  ┌────────────┐  │ │  eqlib/report.py       (HTML/PNG/MD/JSON)  │
│  │ AKShare API │  │ │  eqlib/scientific/     (过拟合/偏差检测)    │
│  │ 本地 CSV    │  │ └─────────────────────────────────────────────┤
│  │ 缓存管理    │  │
│  └────────────┘  │
└──────────────────┘
```

## 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **回测引擎** | `eqlib/engine.py` | 事件循环、调度、订单撮合、组合管理 |
| **数据 API** | `eqlib/data.py` | 历史行情、实时快照、财务数据、A 股特色数据 |
| **交易执行** | `eqlib/trade.py` | 下单、T+1 检查、100 股取整、手续费计算 |
| **绩效分析** | `eqlib/attribution.py` | Sharpe、Alpha/Beta、Brinson 归因、因子分析 |
| **报告生成** | `eqlib/report.py` | HTML 交互式报告、PNG 图表、Markdown、JSON |
| **选股框架** | `eqlib/selection.py` | TopNSelector、MultiFactorSelector、定期调仓 |
| **工具库** | `eqlib/utils/` | 40+ 技术指标、统计分析、资金管理 |
| **通知** | `eqlib/notification.py` | 钉钉/飞书 Webhook 交易信号 |
| **科学验证** | `eqlib/scientific/` | 过拟合检测、统计置信度、偏差检测 |

## 数据流

```text
用户定义策略 → initialize() → run_daily() 注册回调
                                      │
                                      ▼
每个交易日: before_trading_start → handle_data / market_open → after_trading_end
                                      │
                                      ├── 调用 data API 获取行情
                                      ├── 计算信号
                                      ├── 调用 order*() 下单（入队）
                                      │
                                      ▼
                          下一交易日开盘：订单撮合（避免前视偏差）
                                      │
                                      ▼
回测结束 → analyze_returns() → generate_report()
```

## Web Studio 架构

Web 策略工作室在 `eqlib` 之上增加了一层 Web 界面：

- **前端**：React + Vite + TypeScript，使用 Monaco 编辑器、Lightweight Charts
- **后端**：FastAPI，通过 `isolated_runner.py` 在**独立子进程**中运行回测，防止策略代码影响服务器
- **通信**：SSE（Server-Sent Events）实时推送回测日志
- **存储**：SQLite（策略代码和回测结果）+ 文件系统（报告产物）
