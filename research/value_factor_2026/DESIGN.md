# value_factor 2026 — Design (frozen before any run)

Written 2026-11-10, before any run of this strategy. This is the fourth
frozen-design study on this pool and the first to change the **alpha source**
rather than the technical entry rules, per the standing conclusion of
`research/sr_swing_2026/README.md`: rule-based technical entries showed no
edge after costs on this pool; drawdown control worked everywhere. This study
tests a slow fundamental factor with minimal trading machinery.

## Hypothesis

On a liquid large/mid-cap A-share pool, holding the **lowest-valuation
profitable names** (low PE-TTM, low PB), rebalanced monthly, earns more than
CSI 300 over 2024–2026 with drawdown no worse than −25%, and survives 2×
costs. Economic basis: the window's strongest persistent cohort (banks,
energy, SOE dividend names) is exactly the low-PE/low-PB corner of this
pool; a value rank should hold them *continuously*, unlike technical entries
that traded in and out of them.

Deliberate anti-overfitting stance: **no trend gate, no support/resistance,
no per-stock stops, no momentum overlay.** Those were falsified here. The
only risk machinery is a portfolio-level kill switch, kept identical to the
prior studies for comparability.

## Frozen choices

- **Universe**: the 44-name frozen pool from `regime_momentum_2026`
  (static watchlist; survivorship bias bounded by 10 deliberate KNOWN_LOSERS,
  disclosed, not eliminated).
- **Price data**: `data/regime_momentum/` frozen qfq CSVs (offline,
  sha256-recorded). Fills at next open; signals from completed bars.
- **Valuation data**: Baidu `stock_zh_valuation_baidu` PE(TTM) and PB per
  name, frozen by `prefetch_valuation.py` into `data/value_factor/` with
  sha256 manifest. The series is *sampled* (every ~12–18 calendar days
  depending on name); values are carried forward with a **staleness cap of
  21 calendar days** — a name with no fresher sample is ineligible that day.
  Carry-forward uses only past samples (point-in-time safe). The sampling
  grid is a vendor artifact and is disclosed as a limitation.
- **Rebalance**: every 20 trading days (monthly).
- **Eligibility** (checked on rebalance days): PE(TTM) > 0 (profitable),
  PB > 0, fresh valuation sample, price ≥ 3 CNY, 20-day average turnover
  ≥ 1e8 CNY.
- **Score**: composite of cross-sectional percentile ranks —
  `0.5 × rank(PE ascending) + 0.5 × rank(PB ascending)`. Lower is cheaper.
- **Portfolio**: top 8 by score, equal weight 95%/8 ≈ 11.9% each (single
  name cap 15%, gross cap 95%); rank-outs sold at rebalance; no other exits.
- **Portfolio risk only**: kill switch −10% from equity high-water ⇒ flat 20
  sessions (identical to prior studies).
- **Costs**: `examples/_defaults.py` `DEFAULT_ORDER_COST` + 0.1% slippage;
  stress run 2× commission + 0.3% slippage.
- **Cash**: 1,000,000 CNY. Benchmark: CSI 300.
- **Window under test**: 2024-01-01 .. 2026-10-27 (user's target).
  Smoke window (mechanics only, never scored): 2023.
- **Protocol**: the evaluation window is run once. Afterwards only execution
  bugs (wrong fills/prices, dead code) may be fixed and rerun with both runs
  preserved and disclosed — never signal logic. A failed gate is reported
  as-is.

## Gate (declared pre-run)

1. total return > CSI 300 over the same window,
2. max drawdown ≥ −25%,
3. Sharpe ≥ 1.0,
4. stress run total return > 0.

All four or the study is a reported failure.

## Known limitations

Static survivorship-bounded watchlist; qfq price approximation; long-only
cash account; vendor-sampled valuation series with carry-forward staleness
(≤21 calendar days); PE/PB are point-in-time ratios but their EPS/book
components reflect the latest *published* reports, which is realistic for a
live trader; one market sample (2024–2026) — a window whose leadership
(banks/energy) is known, so this study tests whether a *mechanical* value
rank captures it, not whether we can name it in hindsight.
