# sr_swing 2026 — Design (frozen before the first evaluation run)

Written 2026-11-10, before any run of this strategy. Parameters below are
round numbers chosen from prior literature and from the failure attribution of
`research/sr_risk_budget_2026_09` and `research/regime_momentum_2026`. The
evaluation window is run **once**; afterwards only execution bugs (wrong
fills, wrong prices) may be fixed — never signal logic. If the gate fails, the
outcome is reported as-is, same standard as the two prior studies.

## What was learned from the prior failures (design inputs)

1. `sr_risk_budget_2026_09`: strict breakout-retest at S/R produced 38
   signals in 6.7 years and a 23% win rate — death by signal scarcity.
   → This design triggers on *pullbacks to support*, an event that occurs
   far more often than a clean breakout-retest.
2. `regime_momentum_2026`: a market-wide 200-day MA kill switch left the
   book flat 91% of sessions and missed the V-shaped policy rally.
   → This design uses a *per-stock* trend state (leaders turn up long before
   the index) and only *halves* risk when the index is below its MA200 —
   no full kill.
3. Both: costs were never the problem; signal quality was.

## Hypothesis

In A-shares 2024–2026 (crash, V-rally, bull), buying *established uptrends*
at *swing support with rejection confirmation*, with tight ATR stops below
the level and exits at the next resistance, earns more than CSI 300 with a
smaller drawdown, and survives 2× costs.

## Frozen choices

- **Universe**: the 44-name frozen pool from `regime_momentum_2026`
  (13 sectors, 10 deliberate KNOWN_LOSERS; static watchlist, survivorship
  bias bounded and disclosed, not eliminated).
- **Data**: `data/regime_momentum/` frozen qfq CSVs (sha256-recorded);
  offline runs only; fills at next open; signals from completed bars.
- **Window under test**: 2024-01-01 .. 2026-10-27 (user's target).
  Warm-up: 2022–2023 bars from the same frozen files.
  Smoke window (mechanics only, never scored): 2023.
- **Trend gate (per stock)**: close > MA60 and MA20 > MA60.
- **Levels**: swing fractals (5 left / 5 right) over 120 bars, clustered at
  2% tolerance (`eqlib.utils.levels.support_resistance_levels`).
- **Entry (pullback-to-support)**: today's low within 1.0×ATR(20) of the
  nearest support, close back above that support, close above yesterday's
  close, and close in the upper 60% of today's range. Liquidity floor 1e8
  CNY 20-day average turnover; price ≥ 3 CNY.
- **Stop / target**: stop = support − 0.5×ATR, clamped to [1.5%, 8%] under
  entry; target = nearest resistance, requiring reward:risk ≥ 1.8; if no
  resistance overhead, target = entry + 3×risk.
- **Sizing**: risk 0.75% of equity per trade ÷ stop distance; ≤ 15% per
  name, ≤ 6 positions, ≤ 90% gross; risk halves when CSI 300 < its MA200.
- **Exits**: 3×ATR trailing stop (tightens only); target when close ≥
  target; trend break (close < MA60); 60-bar time exit; 5-day cooldown
  after a stop-out; portfolio kill switch −10% from high water ⇒ flat 20
  sessions.
- **Costs**: `examples/_defaults.py` `DEFAULT_ORDER_COST` + 0.1% slippage;
  stress run at 2× commission and 0.3% slippage.
- **Cash**: 1,000,000 CNY. Benchmark: CSI 300 (`000300.XSHG`).

## Gate (declared pre-run)

1. total return > CSI 300 over the same window,
2. max drawdown ≥ −25%,
3. Sharpe ≥ 1.0,
4. stress run total return > 0.

All four or the study is a reported failure.

## Known limitations

Same as prior studies: static survivorship-bounded watchlist, qfq price
approximation, long-only cash account, single market sample. Additionally:
stop/target decisions are evaluated on *closes* and filled next open, so
intraday stop slippage is approximated, not modelled.
