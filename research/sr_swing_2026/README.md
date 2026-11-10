# sr_swing 2026 — Outcome: FAILED the pre-declared gate

**Verdict (gate frozen in DESIGN.md before any run): 1 of 4 criteria met —
the strategy is a reported failure.** Confirmed on the strategy as designed
after an adversarial review caught an execution bug in the first run
(disclosed below). No parameter was ever changed in response to results.

| gate criterion | required | as designed | first run (buggy, kept) | pass |
|---|---|---|---|---|
| total return vs CSI 300 | > +18.02% | **−2.35%** | +0.58% | ✗ |
| max drawdown | ≥ −25% | −12.03% (CSI 300: −20.23%) | −12.12% | ✓ |
| Sharpe | ≥ 1.0 | **−0.56** | −0.35 | ✗ |
| stress (2× comm, 0.3% slip) | > 0 | **−7.96%** | −5.51% | ✗ |

- Design and gate: `DESIGN.md` (written before the first run)
- Evidence: `reports/sr_swing/evaluation/sr_swing_designed{,_stress}/`
  (the designed strategy) and `reports/sr_swing/evaluation/sr_swing{,_stress}/`
  (first run, full-risk variant — immutable, never overwritten)
- Smoke window (2023, mechanics only, never scored): `reports/sr_swing/smoke/`

## What the strategy was

Pullback-to-support in per-stock uptrends: close > MA60 with MA20 > MA60;
buy when the day's low touches the clustered 120-bar swing support (within
1×ATR) and the close rejects it (back above support, above yesterday's close,
upper 60% of the day range); stop 0.5×ATR below the support; target the next
resistance with ≥1.8 reward:risk; risk 0.75% equity per trade (halved while
CSI 300 < MA200); 3×ATR tighten-only trailing stop; ≤6 positions, ≤90% gross;
−10% kill switch. Frozen 44-name pool with 10 deliberate known losers; fills
at next open; completed bars only.

## Adversarial review (independent subagent, 2026-11-10)

The strategy, runner, methodology, and artifacts were reviewed adversarially
against the frozen CSVs and the eqlib source. Headline outcomes:

**Verified clean, with numerical evidence:**
- **No look-ahead bias.** Swing levels are only used after their 5-bar
  right-window confirmation exists inside the frame (verified at the
  boundary); `attribute_history` strictly excludes the signal day; all 277
  fills priced exactly at next-day open × (1 ± 0.001 slippage), each exactly
  one trading day after its signal.
- **State machine reconciles exactly**: 138 exit orders = 138 exit fills =
  138 sells; cooldowns only after stop-outs; kill switch fired once
  (2025-04-07, −10.9%) and resumed after exactly 20 flat sessions.
- **A-share feasibility**: T+1, lot rounding, board/date-aware price-limit
  blocking, stamp duty on sells, min commission all verified against the
  trade log.
- **Accounting**: independent recomputation matched total return, Sharpe,
  drawdown, exposure, and costs to the reported digits.

**One major defect found and fixed:**
`history_bars` omitted `market_ma` (200), so the benchmark frame was tailed
to 128 bars and the CSI300<MA200 risk-halving overlay silently never executed
(fail-open to 1.0 on all 680 sessions — although the index spent 211 of them
below its MA200). The first run therefore measured a *full-risk variant*, not
the frozen design. Fix (one line in `history_bars`, plus fail-loud in the
overlay and a suspended-day freshness guard) was classified an execution bug
under DESIGN.md — signal logic untouched — and the evaluation was rerun once
as `sr_swing_designed` with the overlay verifiably active (`ss_risk_mul=0.5`
on exactly the 211 below-MA200 sessions). Both runs are kept; the gate table
above shows both.

The overlay's measured effect was small and slightly negative (−2.9pp):
halving weak-tape entries removed some of the few winning trades. The failure
conclusion is unchanged and now correctly attributed to the designed
strategy.

**Minor findings (documented, no rerun warranted):**
- Effective per-trade risk averaged ≈0.24% of equity, not the 0.75% budget —
  the 15% name cap binds whenever the stop is tighter than 5% (most entries).
  Both caps were disclosed in DESIGN.md; the budget is a ceiling, not a norm.
- The headline return includes one open position at the window end (600028,
  26,800 sh @ 5.388 avg cost, marked 5.51 ⇒ +3,270 CNY unrealized); closed
  round trips alone net ≈ −26,800 CNY in the designed run. The failure is,
  if anything, understated.
- High-priced names lot-quantize: two 600519 signals sized under one
  100-share lot and were voided by the engine (realistic friction);
  Moutai's three fills were cap-quantized 100-share clips.
- Two comments were corrected (entry ranking description; stale-frame guard
  added for suspended names — verified never triggered on this data).
- eqlib note for future library work (unchanged here): `record()` replaces
  the day's whole snapshot dict, so recorded equity is strategy-reported.

## Why it failed (attribution)

- **The exits tell the story** (both runs, identical): trailing_stop 67,
  trend_break 40, resistance_target 28, time_exit 1, portfolio_halt 2. Stops
  fired 2.4× as often as targets. Win rate 26.1% over 138 round trips
  (49.5/year — the signal-scarcity problem of the prior breakout-retest
  study was solved, and it did not help): with a 1.8 payoff the breakeven
  win rate is 35.7%.
- **The window rewarded holding, not trading**: CSI 300 returned +18.02%.
  The strategy averaged ~25% exposure and was flat on 157 of 680 sessions —
  tight stops below support kept shaking it out of positions mid-trend.
- **Drawdown control worked**: −12.0% vs the index's −20.2%, as did the
  kill switch and the known-loser avoidance (known_loser_pnl ≈ −1.9pp while
  an equal-weight loser basket fell ≈ −20%).
- **Costs were not decisive**: 19,058 CNY (1.9pp) base; the stress run's
  −7.96% shows a thin edge would not survive 2× costs either.

## Standing conclusion across the three studies

Three frozen-design attempts on this pool — breakout-retest S/R
(`sr_risk_budget_2026_09`, 2020–2026), regime momentum
(`regime_momentum_2026`, dev 2023–2024), and support-pullback (this study,
2024–2026) — all failed their gates while their drawdown overlays all
worked as designed. The consistent, honest reading: **on a static large-cap
A-share watchlist, rule-based entries around technical levels have not shown
edge after costs; drawdown control is achievable, alpha was not.** Any
further attempt should change the *alpha source* (universe selection,
fundamental overlay, event drives), not re-parameterize these entries
against the same windows.

## Reproduction

```bash
python research/sr_swing_2026/run_sr_swing.py --period smoke       # mechanics
python research/sr_swing_2026/run_sr_swing.py --period evaluation --label sr_swing_designed
python research/sr_swing_2026/run_sr_swing.py --period evaluation --label sr_swing_designed --stress
```

Python ≥ 3.10, `pip install -e .`, frozen inputs in `data/regime_momentum/`
(regenerate via `research/regime_momentum_2026/prefetch.py` +
`freeze_inputs.py`). Runs assert against network access. Labels make each
frozen code state a new, immutable output directory.
