# Tutorial 02: Backtest Validation

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Read backtest output and risk metrics; identify overfitting, look-ahead bias, and data issues |
    | **Estimated time** | 60–90 minutes |
    | **Prerequisites** | [Tutorial 00](00-getting-started.md), [Tutorial 01](01-first-strategy.md); see [Report Format Guide](../reference/reports-format.md) for the full metric table |

> Deep dive into backtest results, interpret reports and charts, and determine whether a strategy is truly effective.

**Further reading:** [FAQ](../project/faq.md) (blank HTML, JSON field troubleshooting, etc.).

---

## Table of Contents

1. [What Is a Backtest?](#1-what-is-a-backtest)
2. [What a Backtest Tells You](#2-what-a-backtest-tells-you)
   - [2.1 Report Examples in the Repository (`reports/`)](#21-report-examples-in-the-repository-reports)
   - [2.2 How Do Different Strategies' Backtest Reports Look?](#22-how-do-different-strategies-backtest-reports-look)
3. [Interpreting the Backtest Report](#3-interpreting-the-backtest-report)
4. [Interpreting Charts](#4-interpreting-charts)
5. [Risk and Attribution Analysis](#5-risk-and-attribution-analysis)
6. [Determining Whether a Strategy Is Effective](#6-determining-whether-a-strategy-is-effective)
7. [Common Backtesting Pitfalls](#7-common-backtesting-pitfalls)
8. [Portfolio Backtesting](#8-portfolio-backtesting)
9. [Next Steps](#9-next-steps)

---

## 1. What Is a Backtest?

**Backtesting** is "replaying" your trading strategy against historical data to see what would have happened if you had actually traded according to the strategy at the time.

```
Your strategy rules
     +
Historical market data
     ↓
Backtest engine → Simulated trades → Trade log + Portfolio equity curve
```

### What a Backtest Does

- **Validate ideas**: Does the strategy you think works actually make money?
- **Discover flaws**: Are there edge cases you haven't considered?
- **Parameter selection**: Which parameter combination is more reasonable?
- **Quantitative assessment**: Test the strategy on historical data before risking real capital

### What a Backtest Cannot Tell You

- **Guaranteed future profits**: Historical performance does not equal future returns
- **Exact profit amounts**: Backtests have various biases (slippage, liquidity, etc.)
- **Universal effectiveness**: A strategy that works in a bull market may fail in a bear market

---

## 2. What a Backtest Tells You

After running a backtest, you'll get a set of core metrics:

| Metric | Meaning | Benchmark |
|--------|---------|-----------|
| **Total Return** | Total profit/loss percentage over the backtest period | Beating the benchmark (CSI 300) is good |
| **Annualized Return** | Return annualized to a per-year rate | > 10% is acceptable, > 20% is excellent |
| **Annualized Volatility** | Magnitude of return fluctuations | Lower is better (< 25% preferred) |
| **Sharpe Ratio** | Excess return per unit of risk taken | > 1 is good, > 2 is excellent |
| **Max Drawdown** | Largest peak-to-trough decline | Smaller is better (< 15% preferred) |
| **Sortino Ratio** | Like Sharpe, but only considers downside volatility | > 1 is good |
| **Alpha** | Excess return over the benchmark | Positive is good |
| **Beta** | Sensitivity to the broad market | Close to 1 = tracks the market |
| **Win Rate** | May refer to "daily win rate" or "trade win rate" in the HTML, which have different meanings | See below and [Report Format Guide](../reference/reports-format.md) |

> **Note:** `analyze_returns` returns **`win_rate_daily`** (percentage of profitable trading days) and **`win_rate_trade`** (percentage of profitable round-trip trades — FIFO-matched, with a win counted on net P&L after both buy-side and sell-side fees). You cannot directly compare these two numbers to judge strategy quality.

> **Alpha / Beta may show as N/A**: both depend on the benchmark series. When benchmark data is unavailable, `alpha`, `beta`, and `information_ratio` are `NaN` and shown as `N/A` in reports — that is not a computation error, it means there was no benchmark to compare against.

---

## 2.1 Report Examples in the Repository (`reports/`)

A real backtest writes four sets of files (`.html` / `.png` / `.md` / `.json`) under the repository root's **`reports/`** directory. Filenames include timestamps; those with suffixes (e.g., `_19_localdata`) typically correspond to a `report_suffix` or script description in the example scripts.

**Recommended reading:** [Reading Backtest Reports](../how-to/read-reports.md) explains the four report formats. The screenshot below comes from a real run of example [`06_local_data.py`](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/06_local_data.py); the repository ships PNG screenshots only (`docs/assets/tutorials/`) — run the example script locally to generate the interactive `.html`.

![Example: Local data backtest HTML report (19_localdata)](../assets/tutorials/example_report_html_19_localdata.png)

**To open the interactive version yourself:** run `python examples/06_local_data.py` in the repo root, then open the latest `.html` under `reports/` in your browser (the **cumulative return and drawdown charts** include both CSI 300 and SSE Composite dual benchmarks).

The abstract "strategy vs benchmark" line chart is still available at: `../assets/tutorials/sample_equity_vs_benchmark.svg`.

**Cross-referencing the HTML header and metric card readings:** After opening your locally generated `.html`, cross-reference each item against the metric definitions in the [Report Format Guide](../reference/reports-format.md); if the chart area is blank, it's likely due to CDN blocking — see the [FAQ](../project/faq.md).

---

## 2.2 How Do Different Strategies' Backtest Reports Look?

Within the same framework, reports from different strategies have the **same structure but different numbers**. The 6 screenshots below come from completed example runs: identical page layouts, vastly different metric card values. Interactive `.html` files are not shipped with the repository — run the corresponding example script locally to generate one.

> Note: The numbers below are from specific backtest periods and stock selections. **Results will vary significantly** depending on market conditions, time period, and stock selection. These are for illustration only and do not constitute investment advice.

### Bollinger Bands Mean Reversion (Example 15, stock 601088 China Shenhua)

![Bollinger Bands strategy HTML report](../assets/tutorials/example_report_html_bollinger.png)

> The Bollinger Bands strategy excels in range-bound markets — buy when price touches the lower band, sell at the upper band, a natural buy-low-sell-high logic. Actual backtest results will vary with market conditions.

### MACD Trend + Volume Confirmation (Example 16, stock 002594 BYD)

![MACD + volume HTML report](../assets/tutorials/example_report_html_macd_volume.png)

> Tech stocks are highly volatile; a MACD golden cross confirmed by rising volume effectively captures trend initiation points. Actual backtest results will vary with market conditions.

### Grid Trading (Example 18, stock 601398 ICBC)

![Grid trading HTML report](../assets/tutorials/example_report_html_grid.png)

> Grid trading suits low-volatility stocks with clear price ranges — repeatedly "buying low and selling high" within the range. Actual backtest results will vary with market conditions.

### Multi-Factor Stock Selection (Example 17, 7-stock universe)

![Multi-factor stock selection HTML report](../assets/tutorials/example_report_html_multifactor.png)

> The multi-factor model selects the top 3 stocks each week from a pool of 7 based on composite momentum/volume/volatility scores, with high turnover. Actual backtest results will vary with market conditions.

### Single-Stock Strategy Report Page (security 002384)

![Stock selection strategy HTML report](../assets/tutorials/example_report_html_stock_selection.png)

> The same report template serves a low-frequency single-stock strategy: candlesticks with buy/sell markers, cumulative return, drawdown, daily P&L, and trade details. Actual backtest results will vary with market conditions.

### Portfolio Backtest (Example 11, top 3 of 5 candidates)

![Portfolio backtest HTML report](../assets/tutorials/example_report_html_portfolio.png)

> The portfolio example holds the top 3 of 5 candidate stocks ranked by 20-day momentum. A momentum strategy's performance varies significantly depending on market regime — it may perform well in trending markets but poorly in ranging ones. Actual backtest results will vary with market conditions.

**Reading suggestion:** Run any of the example scripts locally (e.g., `python examples/15_bollinger_strategy.py`), open the generated `.html` in your browser, and observe how the same page structure presents different metric cards, candlestick charts, drawdown curves, and trade tables across strategies.

---

## 3. Interpreting the Backtest Report

### 3.1 Running a Backtest to Generate a Report

```python
from eqlib import *

def initialize(context):
    g.security = '601398'
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5,
    ))
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 25, '1d', ['close'])
    if hist.empty or len(hist) < 20:
        return
    ma5 = hist['close'].tail(5).mean()
    ma20 = hist['close'].tail(20).mean()
    price = hist['close'].iloc[-1]

    if price > ma5 > ma20:
        if g.security not in context.portfolio.positions:
            order_value(g.security, context.portfolio.available_cash * 0.95)  # keep a 5% fee buffer
            log.info('BUY %s @ %.3f' % (g.security, price))
    elif price < ma5 < ma20:
        if g.security in context.portfolio.positions:
            order_target(g.security, 0)
            log.info('SELL %s @ %.3f' % (g.security, price))

    record(price=price, ma5=ma5, ma20=ma20)

result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    starting_cash=100000,
    benchmark='000300.XSHG',
    securities=['601398'],
)
```

> **Cost conventions**: these are the current rates (stamp duty 0.05% since 2023-08-28, 0.1% before). Pinning `close_tax` explicitly overrides the engine's built-in date-aware logic; for long history spanning 2023-08-28 use `close_tax=None`. For slippage see the [Configuration API](../reference/api-config.md) (examples default to `FixedSlippage(0.001)`).

### 3.2 Interactive HTML Report

Open `reports/backtest_*.html` in your browser (no local web server needed). From top to bottom, it typically includes: **Summary** → **Metric Cards** (annualized return, Sharpe ratio, max drawdown, Alpha/Beta, etc. — click for tooltips) → **Candlestick & Technical Indicators** → **Cumulative Returns** (strategy vs benchmark) → **Drawdown** → **Daily P&L / Daily Returns** → **Trades, Positions** tabs.

The mapping between each field and the `analyze_returns` dictionary keys is detailed in the [**Report Format Guide**](../reference/reports-format.md); for how to read each section, see [Reading Backtest Reports](../how-to/read-reports.md).

### 3.3 Markdown Report

File path: `reports/backtest_YYYYMMDD_HHMMSS.md`

The report is produced by `generate_report_md`. Its title is `# Backtest Report — 601398` (an em dash followed by the first traded security). Sections appear in this order:

| Section | Contents |
|---------|----------|
| `## Strategy Summary` | Period, initial capital, final value, P&L, benchmark and benchmark return (table) |
| `## Grade Breakdown` | Per-dimension score, grade, and key metrics, with an Overall row at the end |
| `## Performance Metrics` | Annual return, volatility, Sharpe, Sortino, max drawdown, Calmar, Alpha, Beta, information ratio, trade win rate, profit/loss ratio, trade count (with a benchmark comparison column) |
| `## Monthly Returns` | Year × month return matrix + YTD |
| `## Rolling Metrics` | 60-day rolling Sharpe/volatility (quarterly sampled) |
| `## Top 5 Drawdown Periods` | Five deepest drawdowns: start, trough, recovery, depth, duration |
| `## Trade Analysis` | Buy/sell counts, total commission, number of securities traded; multi-stock runs add `### Per-Stock P&L` |
| `## Trade P&L` | FIFO-matched table: `\| # \| Security \| Buy Date \| Buy Price \| Sell Date \| Sell Price \| P&L \|` |
| `## Factor Analysis` / `## Brinson Attribution` | Factor exposure and Brinson attribution (only when data is available) |
| `## Data Sources` | Data sources, risk-free rate convention, and disclaimer |

**Key areas to focus on:**

1. **P&L vs benchmark** (Strategy Summary):
   - Look at both absolute and relative returns
   - Compare with Benchmark Return: if the strategy gained 8% while the CSI 300 gained 15% over the same period, the strategy underperformed

2. **Trading frequency** (Trade Analysis):
   - Too many trades = high turnover = commissions eating into profits
   - Too few trades = signals may not be responsive enough

3. **Per-trade P&L** (Trade P&L):
   - Review each buy and sell price trade by trade; P&L is net of both-side fees
   - If most trades are losing, the signal quality is poor

4. **Commission costs** (Trade Analysis):
   - Compare Total commission against P&L
   - Small trades carry a disproportionately high commission share (5 CNY minimum)

### 3.4 JSON Report

File path: `reports/backtest_YYYYMMDD_HHMMSS.json`

Generated by `generate_report_json`. Top-level keys:

| Key | Contents |
|-----|----------|
| `verdict` | `pass` / `grade` / `score` / `bottleneck` / `action` (`complete` or `adjust_params`) / `summary` |
| `targets` | Per-metric pass/fail checks: `metric`, `value`, `target`, `pass` (failures sorted by `priority`; benchmark-dependent metrics get `pass: null` when unavailable) |
| `diagnostics` | Bottleneck diagnostics |
| `recommendations` | Parameter adjustment suggestions |
| `grade` | Grade details (per-dimension scores) |
| `metrics` | All scalar metrics from `analyze_returns` (`NaN`/`inf` serialized as `null`) |
| `time_series` | `monthly_returns`, `rolling_sharpe_60d`, `rolling_volatility_60d`, `drawdown_periods` |
| `summary` | `start_date`, `end_date`, `initial_capital`, `final_value`, `pnl`, `pnl_pct`, `num_trades`, `securities`, `benchmark`, `benchmark_return` |
| `risk_metrics` | Legacy-compatible metrics subset |
| `cumulative_returns` | Daily `{date, total_value, cumulative_return}` |
| `trades` | Per-fill records: `type`, `date`, `security`, `price`, `amount`, `commission` |
| `positions` | End-of-backtest positions: `amount`, `avg_cost`, `total_value` |
| `chart_data` | Candlestick, volume, cumulative return, and drawdown series for charting |
| `factor_analysis` / `brinson_attribution` | Attribution results (only when data is available) |

```python
import json

with open('reports/backtest_20260503_143000.json') as f:
    report = json.load(f)

# Basic metrics
print("Total return: %.2f%%" % report['summary']['pnl_pct'])
print("Number of trades:", report['summary']['num_trades'])
print("Sharpe ratio: %.2f" % report['metrics']['sharpe_ratio'])

# Daily portfolio value curve
for entry in report['cumulative_returns']:
    print(entry['date'], entry['total_value'], entry['cumulative_return'])

# Target checks: which metrics failed
for t in report['targets']:
    if t['pass'] is False:
        print("Failed:", t['metric'], t['gap'])
```

The JSON report is suitable for further data analysis, such as:
- Calculating maximum consecutive losing days
- Analyzing the ratio of days in-position vs out-of-position
- Plotting the cumulative return curve

### 3.5 How to Read the HTML Interactive Report

The HTML report is the primary backtest analysis tool. After opening it in a browser, the sections and how to read them:

| Section | Contents | How to read |
|---------|----------|-------------|
| **Header summary** | Security, period, initial/final capital, and P&L | Is P&L positive, and how large relative to initial capital? |
| **Summary cards** | Annualized return, excess return, Sharpe, max drawdown, win rate (trade), Calmar | Don't stop at returns — Sharpe and drawdown tell you how much risk bought them. Reference: Sharpe > 1, drawdown < 20%, Calmar > 1 |
| **Detailed metric row** | Annualized volatility, Sortino, Alpha, Beta, information ratio, daily win rate, profit/loss ratio | Positive Alpha + Beta near 1 means genuine excess return, not a directional bet. Alpha/Beta need a benchmark; they show N/A when the benchmark is missing |
| **Candlestick & indicators** | Price line + MA5/MA20 + buy/sell markers + volume; green shading marks holding periods | Are buys near lows? Did price rise while holding? Is trading too dense? |
| **Cumulative returns** | Strategy curve vs benchmark curves (CSI 300 + SSE Composite) | Strategy line consistently above the benchmark = steady outperformance; parallel lines = no alpha |
| **Drawdown curve** | Depth of decline from the historical peak | Look at the deepest point: could you tolerate that period? |
| **Daily P&L / returns** | Per-day profit/loss bars | Consecutive losses? Single-day losses too large? Returns concentrated in a few days? |
| **Tabs** | Trades, end-of-backtest positions, Brinson attribution | Review trades one by one; attribution shows whether returns came from allocation or selection |

**Reading order:** header (did it make money?) → metric cards (Sharpe > 1? drawdown < 20%?) → cumulative return chart (beat the benchmark?) → drawdown curve (worst case acceptable?) → trade table (each trade reasonable?) → attribution (allocation or selection?).

---

## 4. Interpreting Charts

### 4.1 Chart Structure

```
  |                                                     |  Portfolio Value
P |  ---MA5                                              |
r |  ---MA20                                             |
i |  ---Close                                            |
c |                                                      |
e |     [SELL]    [BUY]                                  |
  |    o          o     o[SELL]                          |
  |   / \  ===== / \___/   \                             |
  |  /   \      /           \                            |
  | /     \====/             \=====                      |
  +------------------------------------------------------|-> Date
```

### 4.2 Chart Elements

| Element | Meaning |
|---------|---------|
| **Gray line** | Daily closing price of the stock |
| **Blue line** | 5-day moving average (short-term trend) |
| **Orange line** | 20-day moving average (medium-term trend) |
| **Green circle** | Buy point (annotated below price) |
| **Red circle** | Sell point (annotated above price) |
| **Green shading** | Periods when a position was held |
| **Green line (right axis)** | Total portfolio asset value |

### 4.3 How to Read the Chart

**Good signals:**
- BUY points are typically at price lows (near a golden cross of moving averages)
- SELL points are typically at price highs (near a death cross of moving averages)
- The equity curve (right axis) trends upward overall
- Price shows a clear rise during holding periods (green shading)

**Bad signals:**
- BUY and SELL alternate frequently → Repeatedly "whipsawed" in a range-bound market
- Equity curve trends steadily downward → Strategy is losing money
- No significant price change during holding periods → Ineffective signals

---

## 5. Risk and Attribution Analysis

### 5.1 Comprehensive Risk Metrics

```python
from eqlib import analyze_returns

metrics = analyze_returns(result, risk_free_rate=0.03)

print("Annualized return:    %.2f%%" % (metrics['annual_return'] * 100))
print("Annualized volatility: %.2f%%" % (metrics['annual_volatility'] * 100))
print("Sharpe ratio:          %.2f" % metrics['sharpe_ratio'])
print("Sortino ratio:         %.2f" % metrics['sortino_ratio'])
print("Max drawdown:          %.2f%%" % (metrics['max_drawdown'] * 100))
print("Calmar ratio:          %.2f" % metrics['calmar_ratio'])
print("Alpha:                 %.4f" % metrics['alpha'])
print("Beta:                  %.3f" % metrics['beta'])
print("Daily win rate:        %.2f%%" % (metrics['win_rate'] * 100))
```

> Notes: `win_rate` is a backward-compatible alias for `win_rate_daily`; the round-trip trade win rate is `metrics['win_rate_trade']`, which counts a win on net P&L after both buy-side and sell-side fees. When benchmark data is unavailable, `alpha` / `beta` / `information_ratio` are `NaN` and will print as `nan` — check `math.isfinite` first, or display `N/A` as the reports do.

### 5.2 Brinson Attribution (Multi-Stock Portfolios)

Decomposes returns into three sources:

```python
from eqlib import brinson_attribution

attr = brinson_attribution(result, sector_data={"601398.XSHG": "Financials", "600519.XSHG": "Consumer"})

print("Allocation effect: %.4f  <-- Returns from asset allocation (sector/industry selection)" % attr['allocation_effect'])
print("Selection effect:  %.4f  <-- Returns from individual stock selection" % attr['selection_effect'])
print("Interaction effect: %.4f  <-- Combined effect of allocation and selection" % attr['interaction_effect'])
```

The implementation is a standard single-period Brinson-Hood-Beebower decomposition: the three effects sum **exactly** to portfolio return − benchmark return (`attr['total_active_return']`; see also `portfolio_return` / `benchmark_return` and the per-sector breakdown in `attr['sectors']`). The default benchmark is the equal-weight buy-and-hold return of the universe. Note: **without `sector_data`, all securities share one sector**, so allocation and interaction are identically zero and the entire active return is reported as selection — not a bug, but the correct BHB statement when no sector structure is known.

- **Allocation effect > 0**: Your sector/industry choices were correct
- **Selection effect > 0**: Your stock picks within each sector were correct
- **Interaction effect**: Usually a small adjustment term

### 5.3 Simplified Factor Analysis

```python
from eqlib import simple_factor_analysis

ff = simple_factor_analysis(result)

print("Market Beta:           %.3f  <-- Market sensitivity" % ff['market_beta'])
print("Annualized Alpha:      %.4f  <-- Excess return unexplained by market" % ff['alpha_annual'])
print("Momentum correlation:  %.3f" % ff['momentum_correlation'])
print("Residual volatility:   %.3f" % ff['residual_volatility'])
```

> **Note:** `fama_french_analysis` has been deprecated; use `simple_factor_analysis` instead.

---

## 6. Determining Whether a Strategy Is Effective

### 6.1 Core Evaluation Criteria

| Question | Criterion |
|----------|-----------|
| **Does the strategy make money?** | Total return > 0 |
| **Does it beat the market?** | Strategy return > Benchmark return (CSI 300) |
| **Is risk-adjusted performance good?** | Sharpe ratio > 1 |
| **Is the max drawdown acceptable?** | Max drawdown < your risk tolerance |
| **Is trading frequency reasonable?** | Not daily turnover, nor once every six months |

### 6.2 Comprehensive Evaluation Template

```python
metrics = analyze_returns(result, risk_free_rate=0.03)

checks = []
checks.append(("Return > 0", metrics['total_return'] > 0))
checks.append(("Beat benchmark", metrics['alpha'] > 0))  # alpha is NaN without a benchmark, so this check fails automatically
checks.append(("Sharpe > 1", metrics['sharpe_ratio'] > 1))
checks.append(("Drawdown < 20%", abs(metrics['max_drawdown']) < 0.20))
checks.append(("Trade win rate > 50%", metrics['win_rate_trade'] > 0.50))

print("--- Strategy Evaluation ---")
passed = 0
for name, ok in checks:
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print("  [%s] %s" % (status, name))
print("Passed %d/%d checks" % (passed, len(checks)))
```

### 6.3 Out-of-Sample Validation

```python
# Training set: 2020-2023, used for parameter tuning
result_train = run_strategy(
    initialize, '2020-01-01', '2023-12-31',
    starting_cash=100000, securities=['601398'],
)

# Test set: 2024, used for validation
result_test = run_strategy(
    initialize, '2024-01-01', '2024-12-31',
    starting_cash=100000, securities=['601398'],
)

# If training Sharpe = 2.0, test Sharpe = 0.3 -> overfitting
# If training Sharpe = 1.5, test Sharpe = 1.2 -> parameters are stable
```

---

## 7. Common Backtesting Pitfalls

### 7.1 Overfitting

```
Backtest annualized 50%, live annualized 5%
Cause: Parameters were repeatedly tweaked on historical data, effectively "memorizing" past price movements
```

**How to identify:** Results change drastically with minor parameter tweaks → overfitting

### 7.2 Look-Ahead Bias

```python
# Wrong example: using today's closing price for an open-market decision
# attribute_history returns yesterday's data — this is correct
# But if the strategy uses get_today_close() or any method that includes today's data,
# that constitutes look-ahead bias
```

### 7.3 Survivorship Bias

```
Only tested stocks that are still listed → Ignored delisted / ST (Special Treatment) stocks
→ Backtest results are artificially inflated
```

### 7.4 Ignoring Liquidity

```
Backtest buys 1M CNY of a stock, but the stock's average daily volume is only 500K
→ Impossible to fill in reality, backtest results are invalid
```

### 7.5 Backtest Period Too Short

```
Only backtested 3 months → May have coincided with a bull/bear market
→ Recommend at least 1-2 years, covering different market environments
```

### 7.6 Not Knowing the Engine's Default Behaviors

These defaults directly affect fills; know they exist before reading a report:

| Behavior | Default | Details |
|----------|---------|---------|
| Price-limit interception | On (`check_price_limit=True`) | Buy orders at limit-up open and sell orders at limit-down open are cancelled with a `cancel_reason`; disable via `set_option('check_price_limit', False)` |
| Suspension handling | Same-day order cancellation | A missing bar or zero volume counts as suspended; no orders are routed that day |
| Delisting liquidation | Forced liquidation after 30 trading days without bars | Logged with trade type `DELIST_LIQUIDATE`; tune via `set_option('delist_gap_days', N)` |
| Snapshot data APIs | `FutureWarning` inside a backtest | `get_fundamentals` and friends return the current snapshot; `set_option('avoid_future_data', True)` turns the warning into an error |

---

## 8. Portfolio Backtesting

### 8.1 Single Stock vs Portfolio

| | Single-Stock Backtest | Portfolio Backtest |
|--|----------------------|---------------------|
| Use case | Validate a single strategy logic | Multi-stock rotation, asset allocation |
| API | `run_strategy` / `run_backtest` | `run_portfolio_backtest` |
| Stock universe | One stock | Multiple stocks |
| Position sizing | `context.portfolio.available_cash` | `position_pct` or `position_amount` |

### 8.2 Portfolio Backtest Example

```python
from eqlib import StrategyConfig, run_portfolio_backtest

# Define configuration
config = StrategyConfig(
    starting_cash=200000,
    securities=['601398', '600519', '000858'],
    benchmark='000300.XSHG',
    position_pct=0.33,       # Each stock uses at most 33% of available cash
    start_date='2024-01-01',
    end_date='2024-12-31',
    report_suffix='multi_stock_v1',
)

# Strategy function
def my_strategy(context):
    for sec in context.universe:
        hist = attribute_history(sec, 25, '1d', ['close'])
        if hist.empty:
            continue
        ma20 = hist['close'].tail(20).mean()
        price = hist['close'].iloc[-1]

        if price > ma20 * 1.02:
            order_value(sec, context.portfolio.available_cash * 0.33)
        elif price < ma20 * 0.98 and context.portfolio.positions.get(sec):
            order_target(sec, 0)

# Run the backtest
result = run_portfolio_backtest(config, my_strategy)
```

### 8.3 Portfolio Backtest Output

Below is **illustrative output** (numbers are format examples only — your actual run will differ):

```
==================================================
Portfolio Backtest: 2024-01-01 → 2024-12-31
Universe: ['601398', '600519', '000858']
Rebalance: daily
==================================================
Starting Cash:         200,000.00
Final Value:           215,342.00
P&L:                 +15,342.00 (+7.67%)
Total Trades:              12

--- Per-Stock Summary ---
  600519: 3 buys, 3 sells, net shares 0, realized ¥5,200.00
  601398: 4 buys, 4 sells, net shares 0, realized ¥3,100.00
  000858: 5 buys, 5 sells, net shares 0, realized ¥7,042.00
```

---

## 9. Next Steps

After learning to interpret backtest results, here's what's next:

- **[Tutorial 03: Strategy Optimization & Improvement](03-optimization.md)** — Parameter tuning, portfolio optimization, attribution analysis, avoiding overfitting
- **[Tutorial 05: RSI Mean Reversion Strategy](05-rsi-mean-reversion.md)** — Switch to a different strategy approach: mean reversion
- **[Example 19: Support/Resistance Portfolio Strategy](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/19_sr_portfolio/README.md)** — A complete multi-stock portfolio strategy case study with pre-generated backtest reports for direct review
- **[Tutorial 04: Paper Trading to Live Trading](04-live-trading.md)** — From paper trading to PTrade/QMT live deployment
