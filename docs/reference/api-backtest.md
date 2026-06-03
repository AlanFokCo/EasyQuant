# 回测与模拟盘引擎

> 回测运行、模拟盘交易、调度函数和生命周期回调。

---

## run_strategy

一站式回测 + 报告生成。

```python
run_strategy(initialize_func, start_date, end_date, starting_cash=100000,
             benchmark='000300.XSHG', handle_data=None, securities=None,
             report_dir='reports', use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

返回回测结果 `dict`。

## run_backtest

运行回测（不生成报告）。

```python
run_backtest(initialize_func, start_date, end_date, starting_cash=100000.0,
             frequency='daily', benchmark='000300.XSHG', securities=None,
             use_local=False, max_memory_mb=1024,
             selection_func=None, selection_rebalance='monthly:1')
```

返回 `{"context": Context, "trade_log": list, "recorded_values": dict, "benchmark": str}`。

## run_portfolio_backtest

面向多股票组合的高层回测接口。

```python
run_portfolio_backtest(config, strategy_func, report_dir='reports')
```

### StrategyConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `securities` | `list[str]` | 必填 | 股票池 |
| `start_date` | `str`/`date` | 必填 | 开始日期 |
| `end_date` | `str`/`date` | 必填 | 结束日期 |
| `starting_cash` | `float` | `100000` | 初始资金 |
| `benchmark` | `str` | `"000300.XSHG"` | 基准指数 |
| `position_pct` | `float` | `0.33` | 每只股票最大仓位比例 |
| `position_amount` | `int` | `0` | 固定买入股数 |
| `report_suffix` | `str` | `""` | 报告文件名后缀 |
| `frequency` | `str` | `"daily"` | `"daily"` 或 `"minute"` |

## estimate_memory_mb

估算预加载数据的内存需求。返回 `dict`（`panel_mb`, `close_dict_mb`, `bar_cache_mb`, `total_mb`）。

## run_paper_trade

模拟盘交易，持续运行直到 `Ctrl+C` 终止。

```python
run_paper_trade(initialize_func, starting_cash=100000.0, benchmark='000300.XSHG', interval=60)
```

## record

在策略中记录自定义数据点。

```python
record(price=current_price, ma5=ma5, signal='BUY')
```

## 调度函数

| API | 说明 |
|-----|------|
| `run_daily(func, time='every_bar')` | 每日定时执行 |
| `run_weekly(func, day_of_week=1, time='09:30')` | 每周定时执行 |
| `run_monthly(func, day_of_month=1, time='09:30')` | 每月定时执行 |
| `run_selection(func, rebalance='monthly:1')` | 注册选股函数，按周期执行 |

`rebalance` 格式：`"monthly:N"`（每月第 N 天）、`"weekly:N"`（周几，0=周一）、`"daily"`（每个交易日）。

## 生命周期回调

| API | 说明 |
|-----|------|
| `before_trading_start(func)` | 注册盘前回调 |
| `after_trading_end(func)` | 注册盘后回调 |

---

## 缓存 API

| API | 说明 |
|-----|------|
| `set_cache_dir(path)` | 设置磁盘缓存目录 |
| `fetch_cached(security, start_date, end_date, adjust='qfq')` | 获取数据，优先使用缓存 |

数据源接入建议：保持 API 入参/出参不变，先落盘统一格式再进入回测，采用主备数据源切换与交叉校验。

---

## 日志 API

### 基础日志

```python
log.info(msg)
log.debug(msg)
log.warn(msg)
log.error(msg)
```

### 结构化日志

| API | 说明 |
|-----|------|
| `log.section(title, **fields)` | 标记高层阶段 |
| `log.step(name, status='RUN', **fields)` | 记录步骤状态 |
| `log.progress(current, total, label='Progress')` | 显示进度 |
| `log.action(name, target=None, **fields)` | 记录操作动作 |
| `log.set_level(level)` | 控制详细程度 |
| `log.set_quiet(enabled=True)` | 仅输出 WARNING/ERROR |

---

## 辅助工具 API

| API | 说明 |
|-----|------|
| `engine.get_context()` | 获取当前回测上下文 |
| `engine.get_g()` | 获取全局对象 |
| `engine.get_trade_log()` | 获取交易记录 |
| `engine.get_recorded_values()` | 获取 record() 记录 |

---

## Web Studio API 端点

### `GET /api/v1/runs/{run_id}/report/data`

返回完整的回测报告 JSON 数据（包含所有图表数据数组），用于 Web 控制台中的原生 Lightweight Charts 渲染。

```bash
curl http://localhost:8081/api/v1/runs/<run_id>/report/data
```

返回结构与 `generate_report_json()` 输出的 JSON 一致，包含 `summary`、`risk_metrics`、`cumulative_returns`、`candlestick_data`、`volume_data`、`ma5/20/60_data`、`rsi_data`、`macd_data`、`bb_upper/middle/lower_data`、`drawdown_data`、`pnl_bar_data`、`daily_returns_data` 等全部字段。

---

## 参数化与优化约定

`eqlib` 的 API 可与任意 Python 流程配合（脚本、Notebook、定时任务）。典型调用链：`run_backtest()` → `analyze_returns()` → `brinson_attribution()` → 分析结果 → 修改参数 → 再回测。

策略文件定义 `PARAMS`（当前值）与 `PARAM_RANGES`（搜索空间），由优化脚本读取与更新。每次变更后建议核对：新参数落在范围内、满足交叉约束、未引入前视偏差。
