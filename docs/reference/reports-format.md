# 报告格式规范

> JSON、PNG、HTML、Markdown 报告的字段定义与数据结构。

---

## analyze_returns 指标字典

对 `result = run_backtest(...)` 或 `run_strategy` 的返回值：

```python
from eqlib import analyze_returns

m = analyze_returns(result, risk_free_rate=0.03, trading_days=252)
```

当 `result["recorded_values"]` 不足以构造日净值序列时，函数可能返回 **`None`**，此时 HTML 中部分指标也会缺失。

| 键名 | 含义 |
|------|------|
| `total_return` | 全区间总收益率（基于起止组合价值） |
| `annual_return` | 由日收益几何年化得到的年化收益 |
| `annual_volatility` | 日收益标准差 × √252 |
| `sharpe_ratio` | 夏普比率（年化，扣无风险利率） |
| `sortino_ratio` | 索提诺比率 |
| `max_drawdown` | 最大回撤（负数） |
| `calmar_ratio` | 年化收益 / \|最大回撤\| |
| `alpha` | 年化 Alpha（相对基准） |
| `beta` | Beta |
| `information_ratio` | 信息比率 |
| `win_rate_daily` | 日胜率 |
| `win_rate_trade` | 配对交易胜率 |
| `trade_count` | 完成配对交易次数 |
| `win_count` / `loss_count` | 盈利 / 亏损交易笔数 |
| `profit_loss_ratio` | 盈亏比 |
| `annual_turnover` | 年化换手率（成交额相对规模） |
| `total_commission` | 佣金合计（报告用；净值已反映成本） |
| `net_return` | 与 `total_return` 一致含义（见源码注释） |
| `excess_return` | 策略总收益 − 基准总收益 |
| `benchmark_return` | 基准总收益 |
| `excess_return_max_drawdown` | 超额收益序列最大回撤 |
| `excess_return_sharpe` | 超额收益夏普 |
| `daily_excess_return` | 日超额收益年化均值 |
| `benchmark_volatility` | 基准年化波动率 |

无风险利率默认 **`risk_free_rate=0.03`**（年化 3%），可按研究习惯修改。

---

## Markdown / JSON 报告

- **Markdown**：适合贴到笔记或版本库，快速浏览摘要与成交表。
- **JSON**：适合写脚本批量对比多组参数、画自定义图、接入仪表板。

### JSON 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `metadata` | `object` | 生成时间、数据源、方法论、免责声明 |
| `summary` | `object` | 回测区间、资金、盈亏、交易次数、基准 |
| `risk_metrics` | `object` | 夏普、索提诺、最大回撤、Alpha/Beta 等 |
| `excess_return_metrics` | `object` | 超额收益、超额回撤、超额夏普 |
| `brinson_attribution` | `object` | Brinson 归因（配置/选股/交互效应） |
| `factor_analysis` | `object` | Fama-French 因子暴露 |
| `trades` | `array` | 每笔成交记录 |
| `positions` | `object` | 期末持仓 |
| `cumulative_returns` | `array` | 每日净值序列 |
| `candlestick_data` | `array` | K 线数据（TradingView 格式） |
| `volume_data` | `array` | 成交量柱数据 |
| `ma5_data` / `ma20_data` / `ma60_data` | `array` | 均线数据 |
| `rsi_data` | `array` | RSI(14) 数据 |
| `macd_data` / `macd_signal_data` / `macd_hist_data` | `array` | MACD 线/信号/柱状图 |
| `bb_upper_data` / `bb_middle_data` / `bb_lower_data` | `array` | Bollinger Bands |
| `support_data` / `resistance_data` | `array` | 支撑/阻力 |
| `markers` | `array` | 买卖信号标记 |
| `cum_return_data` | `array` | 策略累计收益率 |
| `ret_hs300_data` / `ret_sse_data` | `array` | 沪深300/上证指数累计收益 |
| `drawdown_data` | `array` | 回撤序列 |
| `pnl_bar_data` | `array` | 每日盈亏柱 |
| `daily_returns_data` | `array` | 每日收益率 |

JSON 顶层字段随版本可能扩展，以生成文件为准。

**读 JSON 时注意：**`summary.num_trades` 多为单边成交条数，与「配对交易笔数」不同，见 [FAQ](../project/faq.md#faq-json-num-trades)。
