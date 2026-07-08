# A-Share Industry Leader Support/Resistance Strategy Design

**Date**: 2026-07-08
**Status**: Strategy direction approved, pending implementation plan
**Scope**: Research and backtest a medium/low-frequency A-share industry leader selection and trading strategy with `eqlib` from 2020 onward

---

## 1. Goal

Design a medium/low-frequency quantitative strategy for A-share industry leaders. The main goals are:

1. Keep the equity curve as stable as possible.
2. Seek to outperform broad benchmarks such as CSI 300 or CSI 800 under controlled risk.
3. Avoid high-frequency and medium/high-frequency trading. Trading frequency should come from daily/weekly trend structures, not from artificial signal suppression.
4. Use support, resistance, valid breakouts, pullback confirmation, and breakdown risk control as the main trading basis.
5. Use scientific, reproducible, no-lookahead calculations for selection, entries, exits, parameter tuning, and period-by-period attribution.

This design does not promise profits. Its purpose is to establish a testable, tunable, reviewable strategy research process and select a final strategy with better historical risk-adjusted quality.

---

## 2. Investment Universe

### 2.1 Stock Pool Principles

The stock pool focuses on industry leaders and large/mid-cap liquid names across:

- Financials: banks, insurers, brokers
- Consumption: liquor, food and beverage, home appliances, duty-free, medical aesthetics
- Healthcare: innovative drugs, CXO, devices, traditional Chinese medicine leaders
- New energy: batteries, vehicles, photovoltaics, storage
- Technology and manufacturing: non-STAR-board tech leaders, electronics manufacturing, automation
- Cyclicals: non-ferrous metals, chemicals, building materials, machinery
- Energy and utilities: coal, power, telecom operators, transportation

Exclude:

- STAR Market: `688xxx`
- Beijing Stock Exchange: common `8xxxxx`, `4xxxxx`, `9xxxxx` BSE-related codes
- ST and *ST stocks
- Long-term suspended or illiquid stocks
- Extremely low-priced stocks and stocks with severe data gaps

ChiNext industry leaders are not excluded by default, such as CATL or East Money.

### 2.2 Benchmarks

Primary benchmark:

- CSI 300: `000300.XSHG`

Auxiliary benchmarks:

- CSI 800 or an available broad-market proxy
- Shanghai Composite as a market environment reference

---

## 3. Strategy Family

The implementation phase will research three candidate strategies and then select the final main strategy.

### 3.1 Defensive Support Leader Strategy

Positioning: defensive, stable, lower drawdown.

Selection logic:

- Select industry leaders whose medium/long-term trend is not broken.
- Prefer names near long-term support with limited downside room and lower volatility.
- Exclude stocks that have broken major support and have not recovered.

Suitable environments:

- Range-bound markets
- Weak rebounds
- Periods where the index lacks direction but structural opportunities exist

Main risks:

- May underperform more aggressive momentum strategies in strong trends.
- Needs timely exits when support fails.

### 3.2 Resistance Breakout Leader Strategy

Positioning: offensive, trend-following, seeking excess returns.

Selection logic:

- Look for industry leaders breaking 60-day or 120-day resistance.
- Breakouts must exceed an ATR buffer to avoid tiny false line crossings.
- Breakout volume must not shrink, and relative strength versus CSI 300 should be positive.

Suitable environments:

- Trending markets
- Structural bull markets
- Periods of expanding industry momentum

Main risks:

- False breakouts can be frequent in range-bound markets.
- If price quickly falls back below the resistance area, risk control must exit.

### 3.3 Breakout Pullback + Market Gate Portfolio Strategy

Positioning: recommended main strategy, balancing stability and offense.

Core idea:

- Entries are not simple chase trades; the strategy waits for a valid breakout or confirmed pullback after breakout.
- Exits are not caused by short-term noise; they occur when support structure, relative strength, or market environment is damaged.
- Portfolio exposure changes with the support/resistance state of the broad market. When the market breaks down, overall risk exposure is reduced.

This strategy is the main candidate for the final strategy.

---

## 4. Support and Resistance Calculations

All support and resistance levels must be formula-based and reproducible. No subjective line drawing is allowed.

### 4.1 Rolling High/Low Channels

Resistance:

- `resistance_60 = highest high over the previous 60 trading days`
- `resistance_120 = highest high over the previous 120 trading days`

Support:

- `support_60 = lowest low over the previous 60 trading days`
- `support_120 = lowest low over the previous 120 trading days`

Calculation requirements:

- Trading decisions for the current day can only use data available before the current day.
- In backtests, historical windows should be retrieved via `attribute_history` so the current close is excluded.

### 4.2 Fractal High/Low Clusters

To avoid pollution from one-off extreme wicks, add fractal support/resistance:

- Fractal high: a day whose high is higher than the highs of `k` days on both sides.
- Fractal low: a day whose low is lower than the lows of `k` days on both sides.
- Resistance zone: recent fractal highs within `N` days that are near current price and repeatedly appear.
- Support zone: recent fractal lows within `N` days that are near current price and repeatedly appear.

Initial parameters:

- `k = 2`
- Fractal window `N = 120`
- Price clustering tolerance `0.8 * ATR_20`

### 4.3 ATR Buffer

ATR filters false breakouts and false breakdowns.

Definition:

- `TR = max(high - low, abs(high - prev_close), abs(low - prev_close))`
- `ATR_20 = 20-day mean of TR`

Valid breakout:

- `close > resistance + atr_multiplier * ATR_20`

Valid breakdown:

- `close < support - atr_multiplier * ATR_20`

Initial parameter set:

- Test `atr_multiplier = 0.3, 0.5, 0.8`

### 4.4 Volume Confirmation

Breakout signals require non-weak volume:

- `volume_ratio = current-day volume / 20-day average volume`
- Valid breakout requires `volume_ratio >= 1.0`
- Stronger signals may require `volume_ratio >= 1.2`

If the backtest entry happens at the next open, the breakout judgment uses the previous trading day's close and volume to avoid lookahead.

---

## 5. Signal Design

### 5.1 Entry Signals

Candidate stocks first pass basic filters:

- Non-ST, not suspended
- Price above the minimum threshold
- Average 20-day turnover meets the liquidity threshold
- Medium/long-term trend is not in an obvious downtrend

There are two entry signal types.

#### A. Valid Resistance Breakout

Conditions:

- Close validly breaks 60-day or 120-day resistance.
- Volume confirmation is not weak.
- 60-day relative strength versus CSI 300 or CSI 800 is positive.
- 20-day volatility is not extremely inflated.

Purpose:

- Capture trend starts.
- Used for offensive allocation.

#### B. Successful Pullback After Breakout

Conditions:

- The stock previously made a valid breakout.
- The breakout level or medium-term moving average turns into support.
- Pullback does not validly break support.
- Price then strengthens again, for example by closing back above the 20-day moving average or showing a volume-supported rebound.

Purpose:

- Higher priority than direct breakout entries.
- Reduces chase risk.
- Naturally makes the strategy medium/low-frequency.

### 5.2 Exit Signals

Exits are triggered by structural damage, not short-term noise.

Clear or reduce position when:

- The stock validly breaks major support.
- A breakout fails and price falls back below the original resistance level while remaining weak.
- Relative strength turns negative and continues deteriorating.
- Volatility expands sharply while price structure weakens.
- The market index validly breaks medium-term support, triggering portfolio-level de-risking.

### 5.3 Trading Frequency Design

The strategy will not add artificial rules that suppress valid trades just to reduce activity. Lower frequency comes from the signal hierarchy itself:

- Support/resistance windows use 60/120 trading days.
- Entries require valid breakout or pullback confirmation.
- Exits require structural breakdown rather than short-term pullbacks.
- Main selection scan is monthly.
- Risk review is weekly and only handles breakdowns, market deterioration, or clear structural failure.

If weekly risk review finds a valid breakdown, the strategy must sell. If no structure has changed, it will not churn positions because of tiny ranking changes.

---

## 6. Portfolio and Exposure

### 6.1 Number of Holdings

Candidate parameters:

- `top_n = 8, 10, 12, 15`

Principles:

- Avoid over-concentration in a few names.
- Do not buy weak signals solely for diversification.
- Cap same-industry exposure to avoid single-industry risk.

### 6.2 Single-Stock Weights

Initial design:

- Equal weight as the baseline.
- Test inverse-volatility weighting, where lower-volatility names receive slightly higher weights and higher-volatility names receive slightly lower weights.

Single-stock maximum weight:

- Initial value `12%`

Single-industry maximum weight:

- Initial value `30%`

### 6.3 Market Gate

Use the broad index's own support/resistance and trend state to decide portfolio exposure:

- Strong market: index above the 120-day moving average and not below 120-day support; target equity exposure 80%-95%.
- Range-bound market: index near key moving averages; target equity exposure 50%-75%.
- Broken market: index validly breaks medium-term support; target equity exposure 20%-50%.

The market gate does not predict the market. It adjusts exposure based on already observed structure.

---

## 7. Backtest and Analysis

### 7.1 Backtest Period

Full period:

- `2020-01-01` to `2026-07-08`

Sub-periods:

- `2020-01-01` to `2021-12-31`
- `2022-01-01` to `2022-12-31`
- `2023-01-01` to `2024-12-31`
- `2025-01-01` to `2026-07-08`

Each period must explain:

- Why the strategy performed well or poorly.
- Which signal types contributed gains.
- Which signal types caused drawdowns.
- Whether it outperformed the benchmark.
- Whether there were issues such as excessive trading, chasing, or false breakouts.

### 7.2 Evaluation Metrics

Core metrics:

- Total return
- Annual return
- Maximum drawdown
- Sharpe
- Sortino
- Calmar
- Win rate
- Profit/loss ratio
- Trade count
- Annualized turnover or approximate turnover
- Excess return versus CSI 300

The final strategy is selected by risk-adjusted return and stability, not by highest return alone.

### 7.3 Parameter Tests

Parameters to test:

- Support/resistance windows: `60`, `120`, `250`
- ATR multipliers: `0.3`, `0.5`, `0.8`
- Volume confirmation: `1.0`, `1.2`, `1.5`
- Momentum/relative-strength windows: `60`, `120`
- Number of holdings: `8`, `10`, `12`, `15`
- Market-gate exposure tiers

Selection standard:

- Do not select the highest-return configuration alone.
- Prefer configurations that are stable across periods, stable in neighboring parameter settings, drawdown-aware, and reasonable in trade count.

### 7.4 Overfitting Control

Use rolling validation:

- Training window: 18-24 months
- Validation window: 6-12 months

Check:

- Whether parameters are stable across adjacent periods.
- Whether a parameter set works only in one market regime.
- Whether the strategy depends on a few stocks for all gains.
- Whether drawdowns concentrate in a specific market state.

---

## 8. Implementation Boundary

The next implementation phase will include:

1. Build the industry leader stock pool module.
2. Implement support, resistance, ATR, volume confirmation, and relative strength calculations.
3. Implement the three strategy families.
4. Run full-period and sub-period backtests with `eqlib`.
5. Output parameter test results.
6. Output the final strategy explanation and runnable strategy script.

Out of scope:

- Minute-level or intraday strategies.
- Margin financing, options, futures, or ETF hedging.
- Fundamental factors that rely on future financial statement data.
- Manually selecting the stock combination with the prettiest backtest result.

---

## 9. Acceptance Criteria

After implementation:

1. The strategy script can run directly.
2. Backtest covers `2020-01-01` to `2026-07-08` or the latest trading day available from the data source.
3. Outputs full-period and sub-period metrics for all three candidate strategies.
4. Outputs the final recommended strategy and rationale.
5. Clearly explains in which periods the strategy performed well or poorly, and why.
6. Clearly explains parameter selection rationale without using single-run highest return as the only criterion.
7. Trading frequency comes from the strategy signal design itself, without high-frequency, medium/high-frequency, or intraday logic.
8. All entry and exit signals use historically visible data and avoid lookahead.

