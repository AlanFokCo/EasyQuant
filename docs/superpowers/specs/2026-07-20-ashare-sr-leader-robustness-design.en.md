# Robustness Design for the A-Share Industry-Leader Support/Resistance Strategy

## Status

- Date: 2026-07-20
- Status: Design approved; written specification awaiting review
- Baseline strategy: `adaptive_composite`
- Baseline period: 2020-01-01 through 2025-12-31
- Baseline result: A / 71.3, 16.54% annual return, -24.28% maximum drawdown, 0.77 Sharpe

## Background

The current `adaptive_composite` raised the full-period grade from B to A, but it still has three material robustness weaknesses:

1. The `risk_adjusted` dimension scores only 38.5 because Sharpe and Calmar remain low.
2. Maximum drawdown is -24.28%, above the target of less than 20%.
3. The 2025 segment receives a D grade, completes no trades, and trails the benchmark by 14.15%.

The next research iteration will prioritize lower drawdown, better behavior in weak segments, and parameter-neighborhood stability instead of maximizing the full-period grade. Annual return may decline from 16.54%, but the target floor is 12%.

## Goals

The design will produce an optional robust variant of the industry-leader strategy and apply these acceptance gates:

- Full-period annual return is at least 12%.
- Full-period maximum drawdown is strictly below 20%.
- The full-period grade remains A, with a score of at least 70.
- The 2025 stress period trails its benchmark by no more than 5%.
- No rolling validation period trails its benchmark by more than 10%.
- At least 60% of neighboring parameter combinations retain at least 10% annual return and no more than 22% maximum drawdown.

These are research gates, not promises of future live performance.

## Non-Goals

- Do not change the shared backtest engine's matching, cost, or grading formulas.
- Do not expand to a dynamic whole-market universe or change how the existing leader universe is assembled.
- Do not introduce intraday data, high-frequency signals, machine learning, or broad random parameter search.
- Do not alter `grade_strategy` to manufacture a higher grade.
- Do not require this iteration to produce a candidate that replaces the current baseline.

## Selected Approach

Three approaches were considered:

1. Adjust only exposure, stops, and existing filters. This is small in scope but is unlikely to fix the lack of primary signals in 2025.
2. Add only portfolio risk budgeting. This should reduce drawdown but can still leave the strategy in cash for long periods.
3. Combine dual-channel selection with portfolio risk budgeting. Preserve the original return source, allow tightly capped fallback holdings when primary signals are scarce, and control total risk with a state machine.

The third approach is selected. The original `adaptive_composite` remains the baseline. New behavior is enabled explicitly by parameters, and disabling it preserves baseline behavior.

## Architecture

The robust strategy has four bounded components:

1. **Primary selector**: Reuse the existing breakout, pullback, support-distance, relative-strength, and volume logic.
2. **Fallback selector**: When primary signals are scarce, add limited positions from leaders with intact trends, positive relative strength, and low volatility.
3. **Portfolio risk budgeter**: Multiply market-state exposure, a market-volatility factor, and a portfolio-drawdown factor to produce the final equity budget.
4. **Robust research selector**: Apply hard gates and rolling validation before comparing candidate scores, instead of selecting solely by the highest full-period grade.

Monthly rebalance data flow:

```text
Completed historical bars
    -> market state and market volatility
    -> primary candidates
    -> fallback candidates when primary supply is insufficient
    -> portfolio risk-state update
    -> final risk budget
    -> volatility-adjusted weights with primary priority and fallback caps
    -> stock, industry, and liquidity limits
    -> rebalance orders
```

The weekly review updates the portfolio drawdown state, applies structural and trailing-drawdown exits, and reduces existing positions when the active risk budget falls.

## Dual-Channel Selection

### Primary Channel

The primary channel preserves the current `adaptive_composite` behavior:

- Support and resistance use only bars completed before the current decision point.
- Breakouts require an ATR buffer, volume confirmation, and positive relative strength.
- Pullbacks require an intact structure, a close above support, and an allowed support distance.
- Ranking combines pullback, breakout, support distance, relative strength, volatility, and volume ratio.

The primary channel always receives the risk budget first. Fallback candidates cannot replace or crowd out positions that pass the primary signal.

### Fallback Channel

The fallback channel activates only when the number of primary candidates is below `min_primary_candidates`. The initial research value is 5, with a limited neighborhood of 4, 5, and 6.

A fallback stock must satisfy all of the following:

- It has not triggered a structural breakdown.
- Its close is above the 120-day moving average.
- Its 60-day moving average is not below its value 20 trading days earlier.
- Its 60-day relative strength versus the benchmark is at least zero.
- Its 20-day volatility is no higher than the median among otherwise eligible stocks.
- It passes the same average-volume, minimum-price, and board-exclusion rules as the primary channel.

Fallback scoring uses only trend slope, relative strength, and low-volatility rewards. It does not reuse breakout or pullback rewards. Fallback candidates fill only slots left by the primary channel, and total fallback exposure initially has a 25% cap. New fallback purchases are disabled in weak markets and in the defensive or protect portfolio states.

The strategy records the entry channel for every holding. Primary positions retain structural-breakdown exits. Fallback positions also use an 8% to 10% trailing drawdown from a recent high. Research starts at 10% to reduce unnecessary stop-driven turnover.

## Portfolio Risk Budget

The final equity budget is:

```text
final equity budget = market-state exposure * market-volatility factor * portfolio-drawdown factor
```

All three factors remain between zero and one. Cash, stock, industry, and liquidity constraints still apply after this calculation.

### Market-State Exposure

Keep the existing `strong`, `neutral`, and `weak` classification and its exposure parameters. The original market-structure classifier does not change.

### Market-Volatility Factor

Compute annualized volatility from the benchmark's latest 20 completed daily returns:

```text
market-volatility factor = clamp(target annual volatility / realized annual volatility, 0.55, 1.00)
```

The initial target is 18%, with a limited comparison of 16%, 18%, and 20%. Low realized volatility never creates leverage; elevated realized volatility progressively reduces exposure.

### Portfolio Drawdown State Machine

The portfolio high-water mark, current episode trough, and risk state are held in strategy runtime state:

| State | Trigger | Drawdown factor | Fallback purchases |
|---|---:|---:|---|
| `normal` | drawdown < 8% | 1.00 | Allowed |
| `cautious` | drawdown >= 8% | 0.75 | Allowed, subject to the fallback cap |
| `defensive` | drawdown >= 12% | 0.50 | Disabled |
| `protect` | drawdown >= 16% | 0.25 | Disabled; only reductions and exits are allowed, with no new entries |

Downgrades take effect immediately. An upgrade requires all of the following:

- The portfolio has recovered at least half of the high-water-to-trough loss for the active episode.
- The market state is not `weak`.
- Benchmark and portfolio state data are complete.

Each weekly review can restore at most one state. After a state upgrade, new positions must still wait for the next normal rebalance.

### Weight Allocation

Eligible candidates receive inverse-volatility initial weights, then the strategy clips them in this order:

1. Allocate to the primary channel first.
2. Keep total fallback weight below its cap.
3. Enforce `max_stock_weight`.
4. Enforce `max_industry_weight`.
5. Keep increases within the liquidity-volume cap.

The strategy does not redistribute residual cash after clipping. This prevents indirect violations of industry and fallback limits.

## Missing Data and Failure Handling

- If benchmark history is missing or insufficient, do not upgrade risk, increase target exposure, or enable fallback selection.
- If a stock lacks sufficient history, skip it instead of substituting zeros or another symbol's data.
- If risk-state data are incomplete, retain the more conservative current state and allow only risk-reducing orders.
- When a newly listed stock has no history in the requested period, preserve the current local-cache short circuit and do not fall back to an implicit network request.
- If no research candidate passes all hard gates, the report explicitly states that no more robust variant was found and retains the A / 71.3 baseline.

## Research and Selection Rules

### Parameter Space

Keep the search finite and interpretable. Search only:

- Primary-signal shortage threshold: 4, 5, and 6.
- Total fallback exposure cap: 20%, 25%, and 30%.
- Fallback trailing drawdown: 8% and 10%.
- Target annual volatility: 16%, 18%, and 20%.
- A small conservative neighborhood around the portfolio drawdown thresholds.

Do not broadly search all original strategy parameters at the same time. The first iteration fixes the primary parameters of the current A-grade baseline and studies only the new robustness components. A local neighborhood around primary parameters may be evaluated only after the new components prove stable.

### Rolling Validation

Evaluate each fixed parameter set across these windows:

- 2020-2022 formation period, with 2023 as validation.
- 2021-2023 formation period, with 2024 as validation.
- 2022-2024 formation period, with 2025 as a stress-validation period.

The formation period only warms up indicators and portfolio risk state; it does not select parameters inside the window. Validation metrics cover only the following validation year. The same fixed parameter set is therefore observed across distinct market regimes. Because the known 2025 weakness informed this design, reports must call it a stress-validation period rather than untouched out-of-sample data.

### Hard Gates and Ranking

Apply every gate in the Goals section before ranking. Rank passing candidates by:

1. Parameter-neighborhood pass rate.
2. Worst validation-period excess return.
3. Full-period Sharpe ratio.
4. Absolute maximum drawdown, lower first.
5. Monthly win rate.
6. Full-period annual return.

The full-period grade is a gate, not the first ranking criterion among passing candidates.

## Report Changes

The research report preserves the current baseline ranking and adds:

- Pass or failure reasons for every hard gate.
- Return, excess return, drawdown, and grade for all three rolling validation periods.
- Parameter-neighborhood pass rate and worst-period results.
- Time spent in each risk state, state triggers, and recoveries.
- Holding count, trade count, average risk exposure, and return contribution for the primary and fallback channels.
- A side-by-side comparison of the baseline and robust candidate.

Channel return contribution uses each prior trading day's channel position weights multiplied by each security's next daily return, accumulated by channel. This attribution is diagnostic and does not change the backtest engine's total-return calculation.

## Test Strategy

### Unit Tests

- Fallback eligibility requires trend, relative strength, volatility, and intact-structure conditions.
- The fallback channel remains disabled when primary candidates are sufficient.
- Primary candidates receive priority, and total fallback weight cannot exceed its cap.
- Inverse-volatility weights still obey stock and industry limits.
- The volatility factor stays between 0.55 and 1.00 and never creates leverage.
- Portfolio drawdowns of 8%, 12%, and 16% produce the expected risk state.
- Downgrades are immediate; recovery is limited to one weekly step and requires loss recovery plus a non-weak market.
- Fallback holdings use the tighter trailing-drawdown exit.
- Missing benchmark or risk data can only maintain or reduce risk.
- Disabling robust behavior preserves the current `adaptive_composite` behavior.

### Integration and Regression Tests

- The research runner evaluates both the current baseline and robust candidates with deterministic ranking.
- A candidate that fails a hard gate cannot become the final selection.
- Reports still render successfully when no candidate passes and clearly retain the baseline.
- Every signal uses only history available before its callback decision point.
- Trading costs remain 0.05% stamp duty, 0.025% commission, and a CNY 5 minimum.
- Regenerate the 2020-2025 HTML, Markdown, CSV, and JSON reports.
- Update both Chinese and English strategy explanations and pass `python scripts/check_doc_sync.py`.
- Run focused strategy tests, the full test suite, example smoke tests, and the documentation build.

## Implementation Boundary

The expected edit scope is limited to:

- `eqlib/strategies/ashare_sr_leader.py`
- `scripts/run_ashare_sr_leader_research.py`
- `tests/test_ashare_sr_leader_strategy.py`
- `docs/explanation/ashare-sr-leader-strategy.md`
- `docs/explanation/ashare-sr-leader-strategy.en.md`
- Generated reports under `reports/ashare_sr_leader/`

Only make a minimal extension to shared reporting interfaces if the existing backtest result cannot support strategy-specific attribution in the research runner. Any shared public API change must be documented separately and reflected in bilingual API references and examples.

## Completion Criteria

Implementation is complete only when all of the following hold:

1. Dual-channel selection, risk budgeting, and recovery state transitions have deterministic tests.
2. Disabling the new behavior leaves the current baseline unchanged.
3. The full research run completes and produces reproducible reports.
4. At least one candidate passes every hard gate, or the report clearly and honestly says none passed and retains the baseline.
5. Chinese and English documentation remain synchronized, relevant tests and repository checks pass, and any unavoidable existing warnings are listed in the handoff.
