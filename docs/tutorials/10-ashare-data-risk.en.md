# Tutorial 10: A-Share Specific Data and Portfolio Risk Control

!!! abstract "Overview"

    | Item | Description |
    |------|-------------|
    | **Goal** | Master A-share specific data APIs and the portfolio risk monitor |
    | **Estimated time** | ~30 minutes |
    | **Prerequisites** | [Tutorial 03](03-optimization.md) (strategy optimization) |

> The A-share market has its own unique microstructure — north-bound capital (north-capital), margin trading, limit up/down boards, restricted share unlocks — signals that either don't exist or take very different forms in overseas markets. This tutorial walks through how to use the four A-share specific APIs provided by `eqlib` to capture these signals, and how to use `PortfolioRiskMonitor` to build a portfolio-level risk control system.

**Documentation index:** [How-To Overview](../how-to/index.md) | **Related example:** [Example 25](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/13_ashare_sentiment.py)

---

## Table of Contents

1. [Why A-Share Specific Data](#1-why-a-share-specific-data)
2. [North-Bound Capital Flow](#2-north-bound-capital-flow)
3. [Margin Trading Data](#3-margin-trading-data)
4. [Limit Up/Down Statistics](#4-limit-updown-statistics)
5. [Restricted Share Unlocks](#5-restricted-share-unlocks)
6. [Portfolio Risk Control: PortfolioRiskMonitor](#6-portfolio-risk-control-portfolioriskmonitor)
7. [Daily Risk Checks and Circuit Breakers](#7-daily-risk-checks-and-circuit-breakers)
8. [Comprehensive Example: North-Bound Capital Strategy with Risk Control](#8-comprehensive-example-north-bound-capital-strategy-with-risk-control)
9. [Summary and Next Steps](#9-summary-and-next-steps)

---

## 1. Why A-Share Specific Data

Traditional quantitative frameworks (such as Zipline, Backtrader) primarily target US equities and provide "generic" data like price-volume and fundamentals. The A-share market's participant structure and trading rules give rise to several **unique signals**:

| Signal | Meaning | Why It Matters |
|--------|---------|---------------|
| **North-bound capital** | Net inflows/outflows of foreign capital via Shanghai-HK and Shenzhen-HK Stock Connect | Regarded as "smart money" by the market; its movements are used to judge short-to-medium-term trends |
| **Margin trading** | Market-wide leverage via margin balance and short-selling balance | Reflects retail and institutional leverage sentiment; surging balances often signal overheating |
| **Limit up/down stats** | Daily count of limit-up and limit-down stocks | Measures market breadth; widespread limit-downs are a systemic risk signal |
| **Restricted share unlock** | Upcoming unlock schedules and market values of restricted shares | Warns of potential selling pressure; stock prices often decline ahead of large-scale unlocks |

Integrating these signals into strategies makes backtests closer to the real A-share environment and reduces "signal blind spots."

---

## 2. North-Bound Capital Flow

### 2.1 API Overview

```python
from eqlib import get_north_money_flow
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | str / datetime | Start date (default: last 30 days) |
| `end_date` | str / datetime | End date (default: today, China timezone) |

**Returns DataFrame**:

| Column | Description | Unit |
|--------|-------------|------|
| `date` | Trading date | YYYY-MM-DD |
| `net_buy` | Net buy amount (Shanghai-HK + Shenzhen-HK combined) | 100M CNY |
| `total_buy` | Total buy amount | 100M CNY |
| `total_sell` | Total sell amount | 100M CNY |

> **Tip**: The data source is Shanghai-HK + Shenzhen-HK Stock Connect combined, cached for 1 hour. Uses China timezone (UTC+8) to determine "today," preventing cross-timezone servers from fetching the wrong date.

### 2.2 Basic Usage: Calculate Rolling Net Buys

```python
from eqlib import get_north_money_flow
from datetime import datetime, timedelta

# Get the last 3 months of data
end_date = datetime.now().date()
start_date = end_date - timedelta(days=90)

north = get_north_money_flow(start_date=start_date, end_date=end_date)

if not north.empty:
    # 5-day and 20-day rolling net buys
    north["rolling_5d"] = north["net_buy"].rolling(5).sum()
    north["rolling_20d"] = north["net_buy"].rolling(20).sum()

    print(north[["date", "net_buy", "rolling_5d", "rolling_20d"]].tail(10))
```

### 2.3 Strategy Application: North-Bound Capital Trend Signal

```python
from eqlib import get_north_money_flow
from datetime import datetime, timedelta

def north_capital_signal():
    """Determine market sentiment based on north-bound capital."""
    north = get_north_money_flow(
        start_date=datetime.now().date() - timedelta(days=60)
    )
    if north.empty:
        return "neutral"

    north["rolling_5d"] = north["net_buy"].rolling(5).sum()
    north["rolling_20d"] = north["net_buy"].rolling(20).sum()

    latest_5d = north["rolling_5d"].iloc[-1]
    latest_20d = north["rolling_20d"].iloc[-1]

    if latest_5d > 50 and latest_20d > 100:
        return "bullish"          # Strong inflow, bullish
    elif latest_5d < -50 and latest_20d < -100:
        return "bearish"          # Strong outflow, bearish
    elif latest_5d > 0:
        return "neutral_bullish"  # Mild inflow
    elif latest_5d < 0:
        return "neutral_bearish"  # Mild outflow
    else:
        return "neutral"

# Usage
signal = north_capital_signal()
print(f"North-bound capital sentiment: {signal}")
```

---

## 3. Margin Trading Data

### 3.1 API Overview

```python
from eqlib import get_margin_data
```

**Returns DataFrame**:

| Column | Description | Unit |
|--------|-------------|------|
| `date` | Trading date | YYYY-MM-DD |
| `margin_balance` | Margin balance (Shanghai + Shenzhen combined) | 100M CNY |
| `margin_buy` | Margin buy amount | 100M CNY |
| `margin_repay` | Margin repayment amount | 100M CNY |
| `short_balance` | Short-selling balance | 100M CNY |

> **Note**: The first row of `margin_repay` is `NaN` (no prior-day balance to calculate from). Use `dropna()` or `fillna(0)` when processing. The formula is: `margin_repay = previous day margin balance + today's margin buy - today's margin balance`.

### 3.2 Calculate Margin Balance Rate of Change

The **marginal change** in margin balance is more meaningful than the absolute value — rapid increases often signal leverage overheating.

```python
from eqlib import get_margin_data
from datetime import datetime, timedelta

end_date = datetime.now().date()
start_date = end_date - timedelta(days=60)

margin = get_margin_data(start_date=start_date, end_date=end_date)

if not margin.empty:
    # Day-over-day rate of change
    margin["balance_change_pct"] = margin["margin_balance"].pct_change()

    # 5-day average change rate
    margin["balance_change_5d"] = margin["balance_change_pct"].rolling(5).mean()

    # Leverage overheating warning: 5-day avg change rate above 0.5%
    latest_change = margin["balance_change_5d"].dropna().iloc[-1]
    if latest_change > 0.005:
        print(f"WARNING: Leverage overheating: margin balance 5-day avg change rate {latest_change:.4%}")
    elif latest_change < -0.005:
        print(f"DELEVERAGE signal: margin balance 5-day avg change rate {latest_change:.4%}")
    else:
        print(f"OK: Leverage sentiment stable: {latest_change:.4%}")
```

### 3.3 Margin Buy Ratio

The ratio of margin buy amount to margin balance measures the **aggressiveness of new leverage**:

```python
if not margin.empty:
    margin["buy_ratio"] = margin["margin_buy"] / margin["margin_balance"]
    print(f"Latest margin buy ratio: {margin['buy_ratio'].iloc[-1]:.4%}")
```

---

## 4. Limit Up/Down Statistics

### 4.1 API Overview

```python
from eqlib import get_limit_up_down_stats
```

**Returns DataFrame**:

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `limit_up_count` | Number of limit-up stocks |
| `limit_down_count` | Number of limit-down stocks |

> **Important limitation**: This API **only supports the most recent 30 trading days**. Beyond that range, a warning is printed and results may be incomplete. Cache validity is 30 minutes (data changes during trading hours).

### 4.2 Systemic Risk Warning

Widespread limit-downs (e.g., exceeding 100 stocks) are a clear signal of market panic:

```python
from eqlib import get_limit_up_down_stats
from datetime import datetime, timedelta

end_date = datetime.now().date()
start_date = end_date - timedelta(days=15)

stats = get_limit_up_down_stats(start_date=start_date, end_date=end_date)

if not stats.empty:
    print("Recent limit up/down statistics:")
    print(stats[["date", "limit_up_count", "limit_down_count"]].tail(5))

    # Systemic risk warning
    latest_down = stats["limit_down_count"].iloc[-1]
    if latest_down > 100:
        print(f"CRITICAL: Systemic risk alert: {latest_down} stocks hit limit-down")
    elif latest_down > 50:
        print(f"WARNING: Weak market sentiment: {latest_down} stocks hit limit-down")

    # Market breadth indicator: limit-up / limit-down ratio
    stats["up_down_ratio"] = (
        stats["limit_up_count"] / stats["limit_down_count"].replace(0, 1)
    )
    avg_ratio = stats["up_down_ratio"].mean()
    print(f"Average limit-up/limit-down ratio: {avg_ratio:.2f}")
```

### 4.3 Using Limit Up/Down Filter in Strategies

```python
def market_breadth_ok():
    """Check if market breadth is normal (limit-down count below threshold)."""
    stats = get_limit_up_down_stats()  # Default: last 30 days
    if stats.empty:
        return True  # Allow by default when data is unavailable

    recent_3d = stats.tail(3)
    avg_down = recent_3d["limit_down_count"].mean()

    return avg_down < 30  # Market is normal when avg limit-downs < 30 over last 3 days
```

---

## 5. Restricted Share Unlocks

### 5.1 API Overview

```python
from eqlib import get_restriction_release
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `days` | int | Forward-looking window in days, default 30. If `None` or < 1, uses default |

**Returns DataFrame**:

| Column | Description | Unit |
|--------|-------------|------|
| `code` | Stock code | 6-digit number |
| `name` | Stock name | — |
| `release_date` | Unlock date | YYYY-MM-DD |
| `release_amount` | Unlock quantity | 10,000 shares |
| `release_value` | Unlock market value | 100M CNY |
| `release_pct` | Proportion of pre-unlock float market cap | — |

> **Tip**: Cache validity is 6 hours (unlock data doesn't change intraday).

### 5.2 View Upcoming Unlocks

```python
from eqlib import get_restriction_release

# Get the next 30 days of unlock schedules
releases = get_restriction_release(days=30)

if not releases.empty:
    # Sort by unlock market value descending
    top_releases = releases.sort_values("release_value", ascending=False)
    print("Top 10 unlock market value in the next 30 days:")
    print(top_releases[["code", "name", "release_date", "release_value"]].head(10))

    # Statistics: count of large-cap unlocks (>1B CNY)
    big_releases = releases[releases["release_value"] > 10]
    print(f"\nStocks with unlock value > 1B CNY: {len(big_releases)}")
```

### 5.3 Exclude Stocks with Upcoming Unlocks During Selection

Large-scale unlocks often create selling pressure and can be excluded during stock selection:

```python
def filter_restricted_stocks(candidate_codes, days=15, value_threshold=5):
    """Exclude stocks with upcoming large-scale unlocks from candidates.

    Args:
        candidate_codes: List of candidate stock codes (6-digit numbers)
        days: Forward-looking window in days
        value_threshold: Unlock market value threshold (100M CNY)

    Returns:
        Filtered code list
    """
    releases = get_restriction_release(days=days)
    if releases.empty:
        return candidate_codes

    # Stocks with unlock value > threshold or unlock ratio > 5%
    risky = releases[
        (releases["release_value"] > value_threshold)
        | (releases["release_pct"] > 0.05)
    ]
    risky_codes = set(risky["code"].tolist())

    filtered = [c for c in candidate_codes if c not in risky_codes]
    excluded = len(candidate_codes) - len(filtered)
    if excluded > 0:
        print(f"Excluded {excluded} stocks with significant unlock risk")

    return filtered
```

---

## 6. Portfolio Risk Control: PortfolioRiskMonitor

When running multiple strategies, per-strategy risk control is not enough — you need a **portfolio-level** perspective to examine inter-strategy correlations, overall VaR, position concentration, and more.

### 6.1 Creating a Monitor

```python
from eqlib import PortfolioRiskMonitor, RiskThresholds

# Use default thresholds
monitor = PortfolioRiskMonitor()

# Or customize thresholds
custom_thresholds = RiskThresholds(
    max_drawdown_yellow=0.12,    # Yellow alert drawdown
    max_drawdown_red=0.18,       # Red alert drawdown
    max_drawdown_kill=0.25,      # Kill-switch drawdown
    correlation_yellow=0.55,     # Yellow alert correlation
    correlation_red=0.70,        # Red alert correlation
    correlation_kill=0.85,       # Kill-switch correlation
    single_stock_max=0.08,       # Max single stock weight
    single_sector_max=0.25,      # Max single sector weight
    small_cap_max=0.15,          # Max micro-cap weight (market cap < 5B CNY)
    var_confidence=0.95,         # VaR confidence level
)
monitor = PortfolioRiskMonitor(thresholds=custom_thresholds)
```

### 6.2 Adding Strategy Backtest Results

```python
from eqlib import run_backtest

# Strategy A: Moving average strategy
result_a = run_backtest(
    initialize_ma,
    start_date="2024-01-01",
    end_date="2024-12-31",
    starting_cash=100000,
)

# Strategy B: Momentum strategy
result_b = run_backtest(
    initialize_momentum,
    start_date="2024-01-01",
    end_date="2024-12-31",
    starting_cash=100000,
)

monitor.add_strategy("MA Strategy", result_a)
monitor.add_strategy("Momentum Strategy", result_b)
```

> **Note**: `add_strategy` receives the result dict returned by `run_backtest()`, which must contain `recorded_values` data. If data is empty or missing, a `ValueError` is raised.

### 6.3 Calculate Portfolio VaR

VaR (Value at Risk) measures the maximum potential daily loss at a given confidence level:

```python
var_amount, var_pct = monitor.portfolio_var(confidence=0.95)
print(f"At 95%% confidence, portfolio daily VaR: {var_amount:,.0f} CNY ({var_pct:.2%})")
```

| VaR Percentage | Risk Level | Recommendation |
|---------------|-----------|----------------|
| < 1% | Low risk | Normal operation |
| 1% - 2% | Moderate risk | Monitor closely |
| > 2% | Elevated risk | Consider reducing positions |

> **Note**: VaR is calculated using the historical simulation method, requiring at least 30 days of daily return data per strategy. Strategies with insufficient data are automatically excluded and logged. When all strategies have insufficient data, `(nan, nan)` is returned.

### 6.4 Strategy Correlation Matrix

High correlation means strategies "move in lockstep," resulting in poor diversification:

```python
corr = monitor.correlation_matrix()
if not corr.empty:
    print("Strategy correlation matrix:")
    print(corr)

    # Check for excessively high correlations
    max_corr = 0.0
    for i in range(len(corr)):
        for j in range(i + 1, len(corr)):
            if abs(corr.iloc[i, j]) > max_corr:
                max_corr = abs(corr.iloc[i, j])

    if max_corr > 0.75:
        print(f"WARNING: Max inter-strategy correlation {max_corr:.2f}, insufficient diversification")
```

| Correlation | Meaning | Recommendation |
|------------|---------|----------------|
| < 0.3 | Low correlation | Ideal, good diversification |
| 0.3 - 0.6 | Moderate correlation | Acceptable |
| > 0.6 | High correlation | Watch for insufficient risk diversification (yellow alert) |
| > 0.85 | Very high correlation | Kill-switch alert |

> **Tip**: When there are fewer than 2 strategies, `correlation_matrix()` returns an empty DataFrame.

### 6.5 Concentration Risk

```python
concentration = monitor.concentration_risk()
print(f"Number of holdings: {concentration['num_holdings']}")
print(f"Max single stock weight: {concentration['max_single_stock']:.2%}")
print(f"Top 3 holdings concentration: {concentration['top3_concentration']:.2%}")
```

| Return Field | Description |
|-------------|-------------|
| `max_single_stock` | Max weight of any single stock in the portfolio |
| `max_single_sector` | Max weight of any single sector in the portfolio |
| `small_cap_pct` | Micro-cap (market cap < 5B CNY) weight |
| `num_holdings` | Total number of stock holdings |
| `top3_concentration` | Combined weight of the top 3 holdings |

---

## 7. Daily Risk Checks and Circuit Breakers

### 7.1 Running the Daily Check

`daily_check()` is the main entry point for risk control. It integrates VaR, correlation, concentration, market regime, and other dimensions into a `RiskReport`:

```python
from eqlib import PortfolioRiskMonitor, check_kill_switch

monitor = PortfolioRiskMonitor()
monitor.add_strategy("MA Strategy", result_a)
monitor.add_strategy("Momentum Strategy", result_b)

report = monitor.daily_check()

print(f"Alert level: {report.alert_level.value}")
print(f"Portfolio VaR: {report.portfolio_var:,.0f} CNY")
print(f"Market regime: {report.regime}")

if report.triggers:
    print("Triggered alerts:")
    for t in report.triggers:
        print(f"  - {t}")

if report.recommendations:
    print("Recommended actions:")
    for r in report.recommendations:
        print(f"  - {r}")
```

### 7.2 Three-Tier Alert System

| Level | Enum Value | Meaning | Action |
|-------|-----------|---------|--------|
| `YELLOW` | `"yellow"` | Monitor | No automatic action; increase observation |
| `RED` | `"red"` | Human intervention needed | Send notification; recommend rebalancing |
| `KILL_SWITCH` | `"kill"` | Automatic circuit breaker | Pause strategy; await manual confirmation |

Trigger conditions (default thresholds):

| Dimension | YELLOW | RED | KILL_SWITCH |
|-----------|--------|-----|-------------|
| Strategy correlation | >= 0.60 | >= 0.75 | >= 0.85 |
| Single stock weight | > 10% | > 20% | — |
| Single sector weight | > 30% | — | — |
| Micro-cap weight | > 20% | — | — |
| Market regime | Volatile market | — | Bear market |

### 7.3 Circuit Breaker Check

`check_kill_switch()` returns a list of actions requiring immediate execution based on the report's trigger conditions:

```python
actions = check_kill_switch(report)

if actions:
    print("WARNING: Actions requiring immediate execution:")
    for action in actions:
        print(f"  {action}")
else:
    print("OK: No circuit breaker actions needed")
```

Example `KILL_SWITCH` level circuit breaker actions:

- "Pause all strategies, await manual confirmation"
- "Reduce positions of high-correlation strategies by 50%"
- "Reduce overweight stock positions"

Example `RED` level recommended actions:

- "Recommend reducing positions of high-correlation strategies"
- "Recommend manual review of strategy status"

### 7.4 Integrating Risk Control in Live Trading

Use the `before_trading_start` callback to run risk checks before each day's market open:

```python
from eqlib import (
    before_trading_start, PortfolioRiskMonitor,
    check_kill_switch, AlertLevel, log,
)

monitor = PortfolioRiskMonitor()

def risk_check_callback(context, data):
    """Pre-market daily risk check."""
    report = monitor.daily_check()

    if report.alert_level == AlertLevel.KILL_SWITCH:
        log.warning(f"CRITICAL: Kill-switch alert! Triggers: {report.triggers}")
        actions = check_kill_switch(report)
        for action in actions:
            log.warning(action)
        # In live trading, this is where you'd call a liquidation function or send an emergency notification

    elif report.alert_level == AlertLevel.RED:
        log.warning(f"RED alert: {report.triggers}")
        for rec in report.recommendations:
            log.info(f"  Recommendation: {rec}")

    elif report.triggers:
        log.info(f"YELLOW: Watch: {report.triggers}")

# Register callback in initialize
def initialize(context):
    before_trading_start(risk_check_callback)
    # ... other initialization
```

> **Note**: Callbacks registered via `before_trading_start` execute before 09:30 each trading day, with signature `(context, data)`. Unlike `run_daily(func, time='09:30')`, it runs before market open, making it suitable for pre-market checks.

---

## 8. Comprehensive Example: North-Bound Capital Strategy with Risk Control

Below is a complete strategy example combining north-bound capital signals with risk checks:

```python
"""North-bound capital strategy with risk control.

Strategy logic:
- North-bound capital 5-day net inflow > 5B CNY AND 20-day net inflow > 10B CNY -> Bullish
- North-bound capital 5-day net outflow > 5B CNY -> Reduce position
- Check market breadth (limit-down count) daily before market open
"""

from eqlib import (
    run_backtest, analyze_returns, order_target, order_value,
    get_north_money_flow, get_limit_up_down_stats,
    before_trading_start, g, log, set_benchmark, attribute_history,
)
from datetime import datetime, timedelta


def initialize(context):
    """Strategy initialization."""
    g.security = "601390"      # China Railway
    g.position_pct = 0.8       # Maximum position ratio
    g.can_trade = True         # Risk circuit breaker flag

    set_benchmark("000300.XSHG")

    # Register pre-market daily risk check
    before_trading_start(before_market_check)


def before_market_check(context, data):
    """Pre-market daily: check north-bound capital + market breadth."""
    current_date = context.current_dt.date()

    # -- 1. North-bound capital signal ---------------------------
    north = get_north_money_flow(
        start_date=current_date - timedelta(days=60),
        end_date=current_date,
    )

    if not north.empty:
        north["rolling_5d"] = north["net_buy"].rolling(5).sum()
        north["rolling_20d"] = north["net_buy"].rolling(20).sum()

        latest_5d = north["rolling_5d"].iloc[-1]
        latest_20d = north["rolling_20d"].iloc[-1]

        # Strong outflow -> reduce position
        if latest_5d < -50 and latest_20d < -100:
            g.position_pct = 0.3
            log.info(
                f"North-bound outflow signal: 5d={latest_5d:.1f}B, "
                f"20d={latest_20d:.1f}B, reduce to 30%%"
            )
        # Strong inflow -> restore normal position
        elif latest_5d > 50 and latest_20d > 100:
            g.position_pct = 0.8
            log.info(
                f"North-bound inflow signal: 5d={latest_5d:.1f}B, "
                f"20d={latest_20d:.1f}B, position 80%%"
            )

    # -- 2. Market breadth check ----------------------------------
    stats = get_limit_up_down_stats(
        start_date=current_date - timedelta(days=5),
        end_date=current_date,
    )

    if not stats.empty:
        recent_down = stats.tail(3)["limit_down_count"].mean()
        if recent_down > 100:
            g.can_trade = False
            log.warning(
                f"CRITICAL: Market panic: avg {recent_down:.0f} limit-downs "
                f"over last 3 days, pausing trading"
            )
        elif recent_down > 50:
            g.position_pct = min(g.position_pct, 0.3)
            log.warning(
                f"WARNING: Weak market: avg {recent_down:.0f} limit-downs "
                f"over last 3 days, limiting position"
            )
        else:
            g.can_trade = True


def handle_data(context, data):
    """Daily trading logic."""
    if not g.can_trade:
        return

    # Moving average signal
    prices = attribute_history(g.security, 20, "1d", ["close"])
    if len(prices) < 20:
        return

    ma5 = prices["close"].iloc[-5:].mean()
    ma20 = prices["close"].mean()

    total_value = context.portfolio.total_value
    target_value = total_value * g.position_pct

    if ma5 > ma20:
        # Short-term MA above -> buy to target position
        order_target(g.security, value=target_value)
    elif ma5 < ma20 * 0.98:
        # Short-term MA significantly below -> liquidate
        order_target(g.security, value=0)


# -- Run backtest --------------------------------------------------
if __name__ == "__main__":
    result = run_backtest(
        initialize,
        start_date="2024-01-01",
        end_date="2024-12-31",
        starting_cash=100000,
    )

    metrics = analyze_returns(result, risk_free_rate=0.03)
    print(f"Annualized return: {metrics['annual_return']:.2%}")
    print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Max drawdown: {metrics['max_drawdown']:.2%}")
```

### Key Points

1. **`before_trading_start` registration**: Called in `initialize` to ensure risk checks run before each day's open; callback signature is `(context, data)`
2. **Signal layering**: North-bound capital provides "big picture" signals (add/reduce position), moving averages provide "entry/exit" timing
3. **Risk circuit breaker**: The `g.can_trade` flag is set in `before_market_check` and checked in `handle_data`
4. **Dynamic position adjustment**: `g.position_pct` floats between 30% and 80% based on market conditions

---

## 9. Summary and Next Steps

### Key Takeaways

| API / Tool | Purpose | Key Notes |
|-----------|---------|-----------|
| `get_north_money_flow` | North-bound capital net inflows/outflows | Unit: 100M CNY; 1-hour cache |
| `get_margin_data` | Margin trading balance and activity | `margin_repay` first row is NaN |
| `get_limit_up_down_stats` | Limit up/down stock count statistics | Only supports last 30 trading days |
| `get_restriction_release` | Restricted share unlock schedule | Unit: 10K shares / 100M CNY; 6-hour cache |
| `PortfolioRiskMonitor` | Portfolio-level risk monitoring | VaR requires >= 30 days of data |
| `check_kill_switch` | Circuit breaker action check | Three-tier alert: YELLOW / RED / KILL_SWITCH |

### Related Examples

- **[Example 25](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/13_ashare_sentiment.py)**: A-share market sentiment indicators — complete demonstration of all four data APIs
- **[Example 07](https://github.com/AlanFokCo/EasyQuant/blob/main/examples/07_lifecycle.py)**: Lifecycle callbacks — detailed usage of `before_trading_start` and `after_trading_end`

### Next Steps

- [Tutorial 04: Paper Trading to Live Trading](04-live-trading.md): Deploy risk-controlled strategies to paper trading
- [Tutorial 09: Strategy Parameter Optimization and Auditing](09-param-optimization.md): Use parameterized methods to optimize this tutorial's strategy parameters
- Try adding `PortfolioRiskMonitor` to your multi-strategy portfolio to check whether inter-strategy correlations are too high
