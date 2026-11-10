# Regime-Momentum 2026 — Outcome: FAILED at development selection

**Verdict (pre-registered, PLAN.md §6): none of the seven candidates qualified
in the development window (2023–2024), so nothing was promoted to the
validation gate. The 2025 validation and 2026 later_check windows remain
unused.** This is the honest negative result the plan committed to report
before any backtest was run: no rescue run, no parameter re-fit, no new sweep.

- Machine-readable verdict: `verdict.json` (produced by `aggregate.py`)
- Hypotheses, frozen windows, gate: `PLAN.md`
- Per-run evidence (equity, trades, events, selections, data sha256):
  `reports/regime_momentum/` (gitignored, reproducible — see below)
- Development runs executed once each on 2026-11-02; verdict aggregated
  2026-11-10.

## 1. Gate evaluation (development, 2023-01-03 .. 2024-12-31)

Qualification required all three: max drawdown ≥ −25%, completed round trips
≥ 3/year, and total return above CSI 300 (+1.63% over the window).

| candidate | Sharpe | total return | CSI 300 | max DD | trips/yr | gate |
|---|---|---|---|---|---|---|
| base | −1.449 | −11.90% | +1.63% | −12.13% | 25.2 | fails (return) |
| breadth | −1.449 | −11.90% | +1.63% | −12.13% | 25.2 | fails (return) |
| inverse_vol | −1.172 | −9.15% | +1.63% | −10.72% | 32.8 | fails (return) |
| monthly | −0.501 | −0.86% | +1.63% | −7.91% | 10.1 | fails (return) |
| no_regime | −1.170 | −32.94% | +1.63% | −40.80% | 168.9 | fails (DD, return) |
| risk_adjusted | −1.529 | −10.72% | +1.63% | −10.80% | 25.2 | fails (return) |
| slow_10_1 | −0.712 | −5.60% | +1.63% | −7.50% | 35.3 | fails (return) |

Every candidate lost to buy-and-hold CSI 300. Per PLAN.md §6 the research
stops here and is reported as a failure.

## 2. What the evidence actually shows

**H1 was supported; H2/H3 were never reachable.** The regime filter did cut
drawdown materially: `base` −12.13% vs `no_regime` −40.80% over the same
window, with average gross exposure 8.1% vs 65.3%. But the filtered strategy
still lost money — the filter prevented disaster, it did not create return.

**The regime filter kept the strategy out of the market almost entirely.**
`base` was risk-on for 71 of 484 sessions, flat on 442 (91.3%), portfolio-halt
for 20, and rebalanced only 11 times. In the 2023–2024 CSI 300 bear, a
200-day-trend filter is nearly always off. That is the intended behaviour —
the cost shows up in H2.

**The momentum leg was a negative-expectancy signal on this pool.** The
`no_regime` ablation traded freely (168.9 round trips/yr, 65% average
exposure) and lost −32.94%. Whatever the regime filter avoided, the raw
6-1 momentum ranking on this 44-name pool actively destroyed value when left
on. H1's falsification clause ("if the filter is the whole story, no_regime
should show similar drawdown") instead showed the filter was the *only* thing
standing between the strategy and a −41% drawdown.

**The year split is the story in miniature** (`base`, yearly slices of the
continuous development run, re-based per PLAN §4):

| year | strategy | CSI 300 | strategy DD | CSI 300 DD |
|---|---|---|---|---|
| 2023 | −3.48% | −11.38% | −3.73% | −21.51% |
| 2024 | −8.73% | +14.68% | −11.88% | −14.41% |

2023: the filter won by staying out. 2024: the policy-driven September rally
reversed the index faster than a 200-day MA with a rising-slope condition can
re-enter; the few trades taken in the recovery lost, and the year gave back
more than 2023's relative gain.

**`breadth` ≡ `base`.** The equity curves are value-identical; the pool's
breadth (fraction above own MA100) never fell below 0.59 on risk-on days
against the 0.50 threshold, so the extra condition never bound. This variant
tested nothing in this sample and should not be counted as an independent
candidate in any multiple-testing accounting.

**Slowing down or re-weighting did not rescue the signal.** `monthly` (fewer
decisions) and `slow_10_1` (longer lookback) were the least-bad variants
(−0.86%, −5.60%) — both still below the benchmark, and both mostly a
less-often-wrong version of the same negative signal. Vol-scaling the rank
(`risk_adjusted`, −1.529 Sharpe) was the worst variant.

## 3. Attribution of the core hypothesis (`base`, development)

- Exit reasons: rank_out 35, regime_filter 10, portfolio_halt 5 — the book was
  turned over by ranking churn and regime flips, not by the trailing stop
  (never hit) or the time exit.
- Trading costs paid: 9,278.57 CNY on 1,000,000 starting cash (~0.93 pp of
  the −11.90%; the loss is signal-driven, not cost-driven).
- 31 of 44 names were traded at least once. Largest net PnL contributions:

| winners | CNY | losers | CNY |
|---|---|---|---|
| 600030 CITIC Securities | +38,327 | 300059 East Money | −22,728 |
| 600028 Sinopec | +21,805 | 603501 Will Semiconductor | −21,214 |
| 601633 Great Wall Motor | +9,250 | 000651 Gree Electric | −18,486 |
| 601088 China Shenhua | +2,914 | 601318 Ping An | −15,864 |
| | | 601628 China Life | −11,781 |
| | | 603259 WuXi AppTec † | −9,881 |

† KNOWN_LOSER. Full per-stock table: `reports/regime_momentum/development/
base/summary.json → per_stock_pnl`.

**Avoidance vs selection on KNOWN_LOSERS** (the ten deliberate post-2021
collapsers; PLAN §7):

| code | strategy PnL (CNY) | buy-and-hold return |
|---|---|---|
| 601012 LONGi | 0 (never held) | −61.65% |
| 002466 Tianqi | 0 (never held) | −56.00% |
| 002460 Ganfeng | 0 (never held) | −48.34% |
| 600009 Shanghai Airport | −4,189 | −38.89% |
| 603259 WuXi AppTec | −9,881 | −30.03% |
| 601111 Air China | 0 (never held) | −24.31% |
| 002714 Muyuan | 0 (never held) | −15.76% |
| 600585 Conch | 0 (never held) | −5.38% |
| 300750 CATL | −645 | +26.72% |
| 600104 SAIC | 0 (never held) | +51.50% |

An equal-weight basket of these ten returned ≈ −20.2% over the window. The
strategy's total loss attributable to them was −14,715 CNY (≈1.5 pp) — the
regime filter plus the positive-momentum requirement dodged the seven worst.
But avoidance was not free: the two losers that recovered hard (CATL +27%,
SAIC +52%) were also missed. The result is best read as *risk avoidance that
worked*, not as selection skill — and risk avoidance alone does not beat the
benchmark.

## 4. Why there is no follow-up run in this study

PLAN.md §6: with no qualifying candidate the research stops — "no rescue run,
no new parameter sweep." The 2025/2026 windows were never executed and stay
pristine. Any successor idea informed by these results (e.g., faster regime
re-entry after V-shaped policy rallies, a different signal family, a
point-in-time universe) is a *new hypothesis*: it needs its own
pre-registration, and if it reuses the 2023–2024 development knowledge it
must not pretend to be out-of-sample on this data.

## 5. Limitations carried from PLAN §8

Static 44-name watchlist with no point-in-time membership/ST ledger; qfq
adjusted prices approximate corporate actions and limit moves; long-only
cash account; one bear market and one policy rally in sample. Additionally,
shown by this outcome: a 200-day trend filter on CSI 300 is structurally
slow to re-enter after policy-driven reversals, and the flat-91% occupancy
makes per-trade statistics thin even before any gate.

## 6. Reproduction

```bash
# one-time, needs network (akshare):
python research/regime_momentum_2026/prefetch.py
python research/regime_momentum_2026/freeze_inputs.py

# offline, one process per candidate (order irrelevant, outputs immutable):
for c in base no_regime breadth risk_adjusted inverse_vol slow_10_1 monthly; do
  python research/regime_momentum_2026/runner.py --candidate "$c" --period development
done

# the gate:
python research/regime_momentum_2026/aggregate.py
```

Requires Python ≥ 3.10 and eqlib installed editable (`pip install -e .`).
Runners assert against any network access; all inputs carry sha256 in both
the per-run summaries and `verdict.json`.
