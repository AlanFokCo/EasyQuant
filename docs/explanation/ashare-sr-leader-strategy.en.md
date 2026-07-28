# A-Share Industry Leader Support/Resistance Strategy

This page explains the implementation behind `eqlib.strategies.ashare_sr_leader`: how it selects stocks from an industry-leader universe, how it evaluates support/resistance structures, how broad-market state controls exposure, and how the research script chooses the final strategy variant.

This is not investment advice and does not promise future performance. It documents the current strategy design and research workflow in the codebase.

## Strategy Positioning

The strategy is neither a pure breakout system nor a pure dip-buying system. Its core idea is:

> Search a liquid A-share industry-leader universe for stocks that have not broken down, are near support or have confirmed a breakout, and still show relative strength versus the benchmark; then size total equity exposure according to broad-market structure, using monthly rebalancing and weekly breakdown checks to reduce churn and drawdown risk.

The implementation is split across two files:

| File | Responsibility |
|------|----------------|
| `eqlib/strategies/ashare_sr_leader.py` | Testable strategy logic: signals, scoring, weights, rebalancing, and risk review |
| `scripts/run_ashare_sr_leader_research.py` | Parameter grid, backtest execution, stability scoring, and report generation |

The latest report at `reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html` did not find a new candidate that passed every robustness gate, so the predeclared fallback retained the `adaptive_composite` baseline parameters. `pullback_market_gate` is no longer the report's final selection.

## Strategy Architecture

The strategy has five layers:

```text
Industry-leader universe
    ↓
Stock-level support/resistance and relative-strength signals
    ↓
Candidate scoring and ranking
    ↓
Broad-market state decides total exposure
    ↓
Portfolio weights, liquidity limits, monthly rebalance, weekly risk review
```

The design intentionally separates "what to buy" from "how much to buy":

- What to buy: stock-level support/resistance, breakout, pullback, relative strength, volatility, and volume.
- How much to buy: broad-market structure, per-stock caps, industry caps, and liquidity limits.

## Stock Universe

The strategy uses predefined A-share industry leaders across sectors such as baijiu, banks, insurance, brokers, healthcare, new energy, telecom, software/hardware, machinery, chemicals, metals, construction, home appliances, and power.

There are two universe layers:

- `DEFAULT_LEADER_UNIVERSE`: the full built-in industry-leader list in the strategy module.
- `RESEARCH_UNIVERSE`: the smaller universe used by the research script for parameter search.

The strategy excludes STAR Market and common Beijing Stock Exchange style codes:

```python
bare.startswith(("688", "8", "4", "9"))
```

This is not a judgment on those stocks. It keeps the research universe closer to main-board and ChiNext-style leaders with more consistent liquidity and trading rules.

## Core Parameters

Parameters are managed by `StrategyParams`. The defaults reflect a medium-to-low-frequency, portfolio-based, risk-constrained style:

| Parameter | Default | Meaning |
|-----------|--------:|---------|
| `level_window` | 120 | Long support/resistance window |
| `short_level_window` | 60 | Short support/resistance window |
| `atr_period` | 20 | ATR buffer window |
| `atr_multiplier` | 0.5 | ATR multiple required for breakouts or breakdowns |
| `volume_window` | 20 | Average volume window |
| `volume_ratio_min` | 1.0 | Minimum volume ratio for breakout signals |
| `rs_window` | 60 | Relative-strength window versus benchmark |
| `top_n` | 10 | Maximum number of holdings |
| `max_stock_weight` | 0.12 | Maximum single-stock weight |
| `max_industry_weight` | 0.30 | Maximum single-industry weight |
| `strong_market_exposure` | 0.90 | Target equity exposure in strong markets |
| `neutral_market_exposure` | 0.65 | Target equity exposure in neutral markets |
| `weak_market_exposure` | 0.35 | Target equity exposure in weak markets |
| `min_relative_strength` | -0.03 | Minimum stock relative strength |
| `max_support_distance` | 0.12 | Maximum allowed distance from support |
| `max_position_drawdown` | 0.0 | Trailing drawdown exit threshold versus a recent position peak; disabled by default |
| `rebalance_threshold` | 0.08 | Rebalance trigger threshold |
| `liquidity_volume_pct` | 0.03 | Maximum incremental buy as a percentage of average traded value |

### Exact Current Baseline Parameters

The fallback baseline is the `adaptive_composite` parameter set identified as `A / 71.3` in the historical baseline report. `A / 71.3` is the established label for that parameter set, not its grade in this rerun; the coverage-audited fresh result is `A / 70.3`, as shown later.

| Parameter | Baseline | Parameter | Baseline |
|-----------|---------:|-----------|---------:|
| `level_window` | 100 | `short_level_window` | 50 |
| `atr_period` | 20 | `atr_multiplier` | 0.45 |
| `volume_window` | 20 | `volume_ratio_min` | 0.90 |
| `rs_window` | 60 | `top_n` | 10 |
| `max_stock_weight` | 0.10 | `max_industry_weight` | 0.25 |
| `strong_market_exposure` | 0.95 | `neutral_market_exposure` | 0.68 |
| `weak_market_exposure` | 0.25 | `min_price` | 0.10 |
| `min_avg_volume` | 100,000 | `min_relative_strength` | -0.015 |
| `max_support_distance` | 0.11 | `max_position_drawdown` | 0.0 |
| `rebalance_threshold` | 0.05 | `liquidity_volume_pct` | 0.04 |
| `robust_enabled` | `False` | `min_primary_candidates` | 5 |
| `fallback_exposure_cap` | 0.25 | `fallback_trailing_drawdown` | 0.10 |
| `fallback_trend_window` | 120 | `fallback_medium_window` | 60 |
| `fallback_trend_lookback` | 20 | `fallback_min_relative_strength` | 0.0 |
| `market_volatility_window` | 20 | `target_annual_volatility` | 0.18 |
| `market_volatility_floor` | 0.55 | `cautious_drawdown` | 0.08 |
| `defensive_drawdown` | 0.12 | `protect_drawdown` | 0.16 |

The baseline keeps `robust_enabled=False`, so primary/fallback channels, portfolio drawdown states, and volatility scaling do not alter its historical execution path. Robust research candidates enable those mechanisms from the same parameter center and compare 16%, 18%, and 20% volatility targets and their neighborhoods.

## Support and Resistance

The strategy computes support and resistance using completed historical windows to avoid look-ahead bias.

`rolling_levels(frame, window)` returns:

- Resistance: the highest high over the previous `window` completed bars.
- Support: the lowest low over the previous `window` completed bars.

The latest current bar is excluded:

```python
completed = frame.iloc[-window - 1:-1]
resistance = completed["high"].max()
support = completed["low"].min()
```

Stock-level signals use both a long and a short window:

- Long window: 120 days by default, representing slower structural boundaries.
- Short window: 60 days by default, representing nearer trading structure.

The final values are:

- Resistance: the lower of long and short resistance, making recent resistance easier to identify.
- Support: the higher of long and short support, emphasizing the nearer defensive level.

This keeps the strategy focused on the structure currently being traded instead of only distant historical extremes.

## ATR Buffer

The strategy does not treat a tiny move above resistance or below support as a valid signal. It adds an ATR buffer.

ATR is based on true range:

```text
TR = max(
    high - low,
    abs(high - prev_close),
    abs(low - prev_close)
)
ATR = rolling_mean(TR, atr_period)
```

A breakout requires:

```text
close > resistance + atr_multiplier × ATR
```

A breakdown requires:

```text
close < support - atr_multiplier × ATR
```

This filters small fluctuations near support/resistance. A larger `atr_multiplier` makes the strategy more conservative; the retained baseline uses `0.45`.

## Relative Strength

The strategy compares each stock with the benchmark, not only with its own history.

Relative strength is:

```text
relative_strength =
    stock_close_today / stock_close_N_days_ago - 1
    -
    benchmark_close_today / benchmark_close_N_days_ago - 1
```

The default window is 60 days.

This avoids buying stocks that merely fell less or rebounded weakly while still underperforming the market. The current baseline uses `min_relative_strength = -0.015`, allowing slight lag while filtering clearly weak names.

## Signal Snapshot

Each stock is converted into a `SignalSnapshot` containing:

| Field | Meaning |
|-------|---------|
| `close` | Current close |
| `resistance` | Computed resistance level |
| `support` | Computed support level |
| `atr` | Current ATR |
| `avg_volume` | Average volume |
| `volume_ratio` | Current volume divided by average volume |
| `relative_strength` | Relative strength versus benchmark |
| `volatility` | Recent 20-day return volatility |
| `support_distance` | Distance from current price to support |
| `resistance_distance` | Distance from current price to resistance |
| `breakout` | Whether the stock has a valid breakout |
| `pullback` | Whether the stock has a valid pullback |
| `breakdown` | Whether the stock has broken down |

Before the snapshot is accepted, the strategy filters out stocks with:

- Insufficient history.
- Price below `min_price`.
- Average volume below `min_avg_volume`.
- Relative strength below the threshold.
- No breakout, no pullback, and too far from support.

This removes unsuitable names early so scoring only handles structurally meaningful candidates.

## Primary and Fallback Channels

With `robust_enabled`, candidates come from two channels and primary candidates always have priority:

- **Primary channel**: support/resistance candidates that pass the `SignalSnapshot` filters, are not broken down, and score above zero.
- **Fallback channel**: enabled only when there are fewer than `min_primary_candidates=5`, the market is not `WEAK`, and portfolio risk is below `DEFENSIVE`; names already in the primary channel cannot be duplicated.

A fallback name must also have complete history, pass price and average-volume filters, close above its 120-day moving average, have a 60-day moving average no lower than 20 trading days earlier, have 60-day relative strength of at least zero, and remain above breakdown. The strategy then keeps only names whose 20-day volatility is no higher than the fallback cross-sectional median and ranks them by medium-term trend, relative strength, and low volatility.

Fallback exposure is capped at 25% of the portfolio and each fallback holding uses a 10% trailing drawdown exit. No fallback risk may be added in `DEFENSIVE` or `PROTECT`; primary candidates continue to use the support/resistance ranking.

## Breakout, Pullback, and Breakdown

The strategy identifies three structural states.

**Breakout**

All conditions must hold:

```text
close > resistance + atr_multiplier × ATR
volume_ratio >= volume_ratio_min
relative_strength > 0
```

This means price has cleared resistance with a volatility buffer, volume is not weak, and the stock has positive relative strength.

**Pullback**

All conditions must hold:

```text
not breakdown
close >= support
support_distance <= max(max_support_distance, 3 × atr_multiplier × ATR / close)
relative_strength >= -0.03
```

This means price remains above support, is not far from the defensive level, and relative strength has not materially deteriorated. The ATR-adjusted support-distance allowance adapts to each stock's price and volatility.

**Breakdown**

Defined as:

```text
close < support - atr_multiplier × ATR
```

Breakdown stocks are excluded. Existing holdings that break down are exited during the weekly risk review.

## Four Strategy Variants

The research script tests four `StrategyKind` variants:

| Variant | Style |
|---------|-------|
| `defensive_support` | Defensive support strategy, preferring near-support, low-volatility, positive-relative-strength stocks |
| `resistance_breakout` | Breakout strategy, preferring valid breakouts, relative strength, and volume |
| `pullback_market_gate` | Pullback confirmation with market exposure gate, preferring pullbacks while still rewarding breakouts |
| `adaptive_composite` | Composite scorer combining pullback, breakout, support distance, relative strength, low volatility, and volume |

No robust candidate passed every gate in this 2020-2025 run, so the rules retained the `adaptive_composite` baseline. This is a fallback decision, not a win by `pullback_market_gate` or a new robust candidate.

## Scoring

Candidates are first converted into snapshots and then scored by variant. If `breakdown=True`, the score is `-100`.

Common components:

```text
low_vol_bonus = max(0, 0.05 - volatility) × 10
rs_score = relative_strength × 100
volume_score = min(volume_ratio, 2.0)
support_score = max(0, 0.20 - support_distance) × 20
breakout_score = 8 if breakout else 0
pullback_score = 10 if pullback else 0
```

The retained baseline's `adaptive_composite` score is:

```text
0.8 × pullback_score
+ 0.9 × breakout_score
+ 0.7 × support_score
+ 0.8 × max(0, rs_score)
+ low_vol_bonus
+ 0.5 × volume_score
- 12 × volatility
```

It combines pullbacks, breakouts, support proximity, positive relative strength, low volatility, and volume, with a direct volatility penalty.

Only stocks with positive scores enter the candidate list, sorted from highest to lowest score.

## Broad-Market State and Exposure

Each month, the strategy classifies the benchmark index and maps that state to total equity exposure.

| State | Condition Summary | Exposure Meaning |
|-------|-------------------|------------------|
| `STRONG` | Index breaks above resistance, or trades above its moving average while holding support | Use strong-market exposure |
| `NEUTRAL` | No clear breakdown and no strong confirmation | Use neutral-market exposure |
| `WEAK` | Index breaks below support beyond the ATR buffer | Use weak-market exposure |

This is the market gate. It does not choose the stocks; it controls how much risk the whole portfolio should take.

The current baseline maps exposure as:

```text
STRONG  → 95%
NEUTRAL → 68%
WEAK    → 25%
```

Even if stock-level signals look attractive, the strategy de-risks heavily when broad-market structure is weak.

## Portfolio Drawdown States and Volatility Scaling

Robust candidates add high-water portfolio drawdown states on top of broad-market exposure:

| State | Portfolio Drawdown Trigger | Exposure Multiplier |
|-------|---------------------------:|--------------------:|
| `NORMAL` | Below 8% | 1.00 |
| `CAUTIOUS` | At 8% | 0.75 |
| `DEFENSIVE` | At 12% | 0.50 |
| `PROTECT` | At 16% | 0.25 |

Downgrades are immediate. Recovery requires a non-`WEAK` market, complete risk data, and recovery of at least half the loss from the episode high-water mark to its trough; each weekly review can recover at most one state.

Volatility scaling uses the annualized standard deviation of the benchmark's latest 20 completed daily returns:

```text
volatility_factor = clamp(target_volatility / realized_volatility, 0.55, 1.00)
final_exposure = market_exposure × volatility_factor × drawdown_multiplier
```

The research center target is 18%, with neighboring 16% and 20% targets; the floor is fixed at 0.55 and the factor never adds leverage. Incomplete data may reduce risk but cannot authorize an increase.

## Portfolio Construction

After ranking candidates, the strategy builds target weights:

1. Select at most `top_n` stocks.
2. Compute base weight as `exposure / count`.
3. Cap each stock at `max_stock_weight`.
4. Cap each industry at `max_industry_weight`.
5. Keep valid existing holdings first, then fill remaining slots with new candidates.

For the current baseline:

- At most 10 holdings.
- Maximum single-stock weight: 10%.
- Maximum single-industry weight: 25%.

This prevents excessive concentration in one leader or one sector.

## Rebalancing and Liquidity Limits

The strategy does not trade on every tiny target-weight change. `should_rebalance_position()` compares current value with target value:

```text
drift = abs(target_value - current_value) / total_value
```

Trading only happens when `drift >= rebalance_threshold`. The current baseline threshold is `5%`.

New buys and increases are also capped by liquidity:

```text
liquidity_cap = close × avg_volume × liquidity_volume_pct
```

The target value cannot exceed current position value plus this liquidity allowance. Sells and reductions are not capped because they reduce risk.

## Scheduling and Risk Review

`make_initialize()` builds the EasyQuant `initialize(context)` callback.

Initialization:

1. Sets the benchmark.
2. Sets A-share trading costs.
3. Stores strategy parameters, universe, and benchmark in `g`.
4. Registers monthly scan and weekly risk review callbacks.

Schedule:

| Frequency | Callback | Purpose |
|-----------|----------|---------|
| First trading day of each month, 09:30 | `monthly_scan` | Classify market state, rank stocks, compute weights, rebalance |
| Every Friday, 09:30 | `weekly_review` | Check held positions for structural breakdown and exit broken names |

Monthly rebalancing lowers turnover. Weekly risk review exits holdings whose structure has failed.

When `max_position_drawdown` is enabled, the weekly review also applies a trailing drawdown guard. It uses the recent completed close peak over `short_level_window` trading days as the reference; if the current close falls more than the threshold from that peak, the position is exited. The default value is `0.0`, meaning disabled. The `drawdown-controlled` candidate uses `0.12`.

## Trading Costs

The strategy uses trading-cost settings close to common A-share assumptions:

```python
OrderCost(
    open_tax=0,
    close_tax=0.0005,
    open_commission=0.00025,
    close_commission=0.00025,
    close_today_commission=0,
    min_commission=5,
)
```

Meaning:

- No stamp duty on buys.
- 0.05% stamp duty on sells.
- 0.025% commission on buys and sells.
- Minimum commission: 5 CNY.

This matches the default example trading-cost convention.

## How the Research Script Selects the Best Strategy

`scripts/run_ashare_sr_leader_research.py` runs the traditional parameter grid and robust seeds with `robust_enabled`, then applies staged gates rather than directly selecting the highest return or stability score.

### Full-Period Hard Gates

A robust candidate must satisfy all three conditions from 2020-01-01 through 2025-12-31:

- Annual return of at least 12%.
- Absolute maximum drawdown strictly below 20%.
- Grade score of at least 70, which is grade A.

Only robust candidates that pass all three proceed. The stability score remains a diagnostic and ranking measure for traditional candidates:

```text
1.5 × annual_return
+ 0.25 × sharpe
+ excess_return
- drawdown_penalty
- undertrade_penalty
- churn_penalty
```

Penalties include:

- Drawdown above 20%.
- Too few trades, which can indicate an accidental non-trading result.
- More than 120 trades, which indicates excessive churn.

### Rolling Validation and Neighborhood Stability

Up to three full-period finalists continue through:

- 2023 window: run 2020-2023 and inspect 2023; excess return must be at least -10%.
- 2024 window: run 2021-2024 and inspect 2024; excess return must be at least -10%.
- 2025 window: run 2022-2025 and inspect 2025; excess return must be at least -5%.

Because 2025 participates in candidate selection and gating, it is a pressure or stress-validation period, never untouched out-of-sample data.

Neighborhood tests vary minimum primary count across 4/5/6, fallback exposure cap across 20%/25%/30%, fallback trailing drawdown across 8%/10%, volatility target across 16%/18%/20%, and drawdown thresholds across 7%/11%/15% and 9%/13%/17%. Each neighbor must deliver at least 10% annual return with absolute maximum drawdown no greater than 22%; at least 60% of neighbors must pass.

A candidate may replace the baseline only after passing the full-period, rolling-validation, and neighborhood gates. Otherwise the script retains the exact `BASELINE_ADAPTIVE_PARAMS` and writes `selection_reason = baseline_retained_no_robust_candidate`. This is a predeclared honest fallback and never relabels a failed result as a robust win.

## 2020-2025 Report Variant

The coverage-audited full research run on 2026-07-26 found no robust candidate that passed the first full-period gate: all ten robust candidates triggered both `annual_return_below_12pct` and `grade_below_a`, so the designed pipeline did not proceed to rolling or neighborhood evaluation. It retained the exact `adaptive_composite` baseline historically identified as `A / 71.3`; the fresh measurement of that same parameter set is `A / 70.3` under the current data and code state.

The first selected full-period row in `summary.json` and the native report records:

| Metric | Value |
|--------|------:|
| Selection reason | `baseline_retained_no_robust_candidate` |
| Strategy variant | `adaptive_composite` |
| Backtest period | 2020-01-01 to 2025-12-31 |
| Total return | 125.91% |
| Benchmark return | 11.50% |
| Excess return | 114.41% |
| Annual return | 14.66% |
| Annual volatility | 16.60% |
| Sharpe | 0.73 |
| Sortino | 1.06 |
| Max drawdown | -20.27% |
| Grade | A / 70.3 |
| Trade count | 35 |
| Raw trade count | 78 |

This selected row meets the annual-return and grade-A gates, but its -20.27% maximum drawdown misses the strict “absolute drawdown below 20%” gate. It also keeps `robust_enabled=False`, so selection remains an honest fallback rather than a win for the new robustness mechanisms. The standalone 2025 stress-validation period returned 6.68% annualized with -9.74% maximum drawdown and -14.57% excess return, still materially lagging the benchmark, so it cannot be described as an untouched out-of-sample win.

Generated results live under `reports/ashare_sr_leader/`: `summary.json`, `summary.csv`, `final_report.md`, `final_report.html`, and `eqlib_best_backtest_2020_2025.html`. Together they record baseline retention, not a robust-candidate victory.

## Suitable Market Conditions

The strategy is better suited to:

- Structural opportunities in large industry leaders, without a broad one-way market collapse.
- Strong or neutral index conditions where selected stocks maintain relative strength.
- Pullbacks that hold support, giving the strategy a definable risk point.
- Sector rotation where the candidate pool can rotate toward stronger leaders.

It can struggle in:

- Fast one-way selloffs where support levels fail repeatedly.
- High-volatility ranges with frequent false breakouts.
- Markets led by small caps or theme stocks rather than industry leaders.
- Weak-index environments where a few stocks surge, because the market gate limits exposure.

## Difference from a Basic Support/Resistance Strategy

Many support/resistance systems buy near support, buy breakouts, and sell breakdowns. This implementation adds several constraints:

| Dimension | Basic S/R Strategy | This Strategy |
|-----------|--------------------|---------------|
| Universe | Arbitrary stocks | Predefined industry leaders |
| Levels | Single window or manual levels | Completed 120-day and 60-day windows |
| Signal validity | Price touches or crosses a level | ATR buffer, volume ratio, relative strength |
| Total exposure | Often fixed | Controlled by broad-market structure |
| Portfolio constraints | Often limited | Stock, industry, liquidity, and rebalance caps |
| Risk control | Stock stop-loss | Weekly structural breakdown review |
| Parameter choice | Subjective | Candidate grid and stability score |

## Key Risks and Limitations

1. **Industry-leader universe bias**  
   A predefined universe may include companies that look successful in hindsight. Production-grade research should consider point-in-time tradable universes.

2. **Support/resistance is descriptive, not causal**  
   Support and resistance describe historical price structure. They do not guarantee future rebounds or successful breakouts.

3. **Monthly rebalancing can react slowly**  
   Monthly scans reduce turnover but may miss fast regime shifts.

4. **The market gate sacrifices some upside**  
   Weak-market de-risking controls drawdown but can miss strong counter-trend stocks.

5. **Parameters come from historical backtests**  
   The retained `adaptive_composite` baseline reached `A / 70.3` in the current backtest, but its maximum drawdown narrowly missed the 20% hard gate and the 2025 stress-validation period materially lagged the benchmark. New out-of-sample tests, walk-forward validation, and parameter sensitivity checks are still needed.

6. **Data processing matters**  
   A-share daily bars, suspensions, adjustments, volume, and index data can materially affect signals and fills.

## Recommended Code Reading Order

To understand the implementation from code, read in this order:

1. `StrategyParams`: parameters and default style.
2. `rolling_levels()` and `compute_atr()`: support/resistance and volatility buffer.
3. `build_signal_snapshot()`: stock-level filtering and signal construction.
4. `score_snapshot()`: scoring differences across variants.
5. `classify_market()` and `market_exposure()`: market exposure gate.
6. `target_weights()` and `rebalance_portfolio()`: portfolio construction and rebalancing.
7. `_risk_review()`: weekly breakdown exit.
8. `make_initialize()`: EasyQuant lifecycle registration.
9. `candidate_param_grid()` and `stability_score()`: research-time variant selection.

## Summary

`ashare_sr_leader` is a relatively conservative A-share industry-leader portfolio strategy:

- Support/resistance defines tradable structures.
- ATR, volume, and relative strength filter noise.
- Broad-market state controls total exposure.
- Stock, industry, and liquidity caps control concentration.
- Monthly rebalancing and weekly breakdown review reduce churn and structural risk.
- Stability scoring selects parameters instead of simply maximizing return.

The 2020-2025 report does not conclude that a new variant won; it retains the `adaptive_composite` baseline under the predeclared fallback rule. The coverage-audited grade improved to `A / 70.3`, but the selected baseline disables the robustness extension and no robust candidate passed the hard gate, so these mechanisms still must not be interpreted as validated robust return capability.
