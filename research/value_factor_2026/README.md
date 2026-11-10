# value_factor 2026 — Gate: 3/4 (Sharpe 0.967 < 1.0), formally FAILED

**Verdict (gate frozen in DESIGN.md before any run): the strategy passed 3 of
4 criteria and formally fails the gate as declared.** No parameter was changed
after seeing results; the evaluation window was run exactly once. This is
nonetheless the first of the four studies on this pool with a positive,
cost-surviving expectancy — the narrow Sharpe miss is reported, not rounded
away.

| gate criterion | required | observed | pass |
|---|---|---|---|
| total return vs CSI 300 | > +18.02% | **+54.55%** (+36.5pp excess) | ✓ |
| max drawdown | ≥ −25% | **−14.79%** (CSI 300: −20.23%) | ✓ |
| Sharpe | ≥ 1.0 | **0.967** | ✗ |
| stress (2× comm, 0.3% slip) | > 0 | **+51.96%** | ✓ |

- Design and gate: `DESIGN.md` (written before the run)
- Evidence: `reports/value_factor/evaluation/value_factor{,_stress}/`
  (summary.json with data sha256, equity/trades/events CSVs, selections.json)
- Valuation inputs: `data/value_factor/` (Baidu sampled PE-TTM/PB, frozen
  with sha256 manifest, carried forward ≤ 21 calendar days)
- Smoke window (2023, mechanics only, never scored):
  `reports/value_factor/smoke/`

## What the strategy was

Monthly (20-trading-day) rebalance into the 8 cheapest *profitable* names of
the frozen 44-name pool: composite of cross-sectional percentile ranks of
PE(TTM) and PB, requiring PE>0, PB>0, fresh valuation sample, price ≥ 3 CNY,
20-day turnover ≥ 1e8 CNY. Rebalance-time targets are equal weight ≈ 11.9%
each with 15%/95% order-time caps; winners are never trimmed, so the *held*
book drifts (see review finding F2 for the realized shape). No trend gate, no
per-stock stops — exits on rank-out only. Portfolio-level kill switch (−10%
from high water ⇒ flat 20 sessions) identical to prior studies. Fills at next
open; completed bars only.

## Yearly slices (continuous run, re-based per year)

| year | strategy | CSI 300 | strategy DD | CSI 300 DD | strategy Sharpe |
|---|---|---|---|---|---|
| 2024 | **+41.04%** | +14.68% | −9.84% | −14.41% | 1.98 |
| 2025 | +16.06% | +17.66% | −7.03% | −10.49% | 1.03 |
| 2026 (to 10-27) | −5.58% | −12.54% | −14.79% | −20.23% | −0.76 |

The pattern matches the hypothesis: the value rank *picked* the window's
leadership at essentially every rebalance — ICBC, CCB, CMB at 33/33, ABC and
Ping An at 32/33 — instead of trading in and out of it (positions were flat
during the single 20-session halt, 2026-06-29..07-24). 2024 supplied most of
the excess; 2025 kept pace in a growth-led tape; 2026's pullback hit banks
too but the strategy still beat the index by 7pp.

## Attribution (evaluation window)

- Per-stock net PnL leaders (realized FIFO round trips only — the 8 open end
  positions contribute ≈ +79k unrealized, not in these figures): ABC +127.5k,
  ICBC +81.9k, CCB +78.8k, SAIC +74.0k, CMB +56.0k, Ping An +49.3k. Losses:
  Shanghai Intl Port −21.7k, Conch −10.5k, Baosteel −10.4k, Tianqi −4.6k.
- Known-loser interaction was **positive** this time (+58.9k realized): the
  value rank bought recovering losers cheap (SAIC) and never picked the
  still-collapsing ones — LONGi, Ganfeng, WuXi, CATL, Muyuan, Air China and
  Shanghai Airport were never selected (verified against selections.json).
- Activity: 34 round trips (12.2/yr), 33 rebalances, costs 5,708 CNY
  (0.57pp — cheap because monthly and drift-tolerant). Win rate 70.6%.
- Exposure: 91.4% average; 24 unique out-of-market sessions (the 20-session
  halt overlaps the zero-position days).

## Adversarial review (independent subagent, 2026-11-10)

Reviewed against the frozen CSVs and eqlib source; every headline number
reproduced exactly from the artifacts. Three-axis verdict: **accuracy PASS**
(no look-ahead in the price or the valuation path; all 84 fills exactly
next-day open × (1±0.001), stress × (1±0.003); sha256 of inputs and of the
producing code all verified), **soundness PASS with the qualifications
below**, **feasibility PASS at this size** (≤0.11% of daily volume per fill).

Findings, and what was done about them:

- **F2 (major, descriptive)** — "equal weight / 15% cap / 95% gross" describes
  *order-time targets*, not the held book. Exits are rank-out-only and winners
  are never trimmed, so the realized portfolio drifted: min/max weight ratio
  averaged 0.75 (bottom 0.37), single-name weight peaked at 18.25% (ABC,
  2025-10-28), and gross exceeded 95% on 304/680 sessions (max 95.42%). The
  gate metrics are computed on the realized book, so the verdict stands; the
  wording here and in DESIGN.md is corrected/disclosed.
- **F3 (major, latent, zero impact this run)** — kill-switch exits blocked by
  a limit-down open or suspension would have deadlocked the halt (exits never
  re-submitted, resume requiring no positions never met). Inherited from the
  prior studies' pattern; **fixed in `value_strategy.py` post-review** and
  verified behavior-neutral on this data by a rerun whose equity curve is
  byte-identical (`reports/value_factor/evaluation/value_factor_f3fix_verify/`;
  all 8 halt exits had filled cleanly at the first attempt on 2026-06-29).
- **F1 (minor outcome, mechanism worth disclosing)** — the 601857 entry of the
  2024-09-30 rebalance opened exactly limit-up on 2024-10-08; the engine
  cancelled the buy and nothing retried (only exit orders are tracked), so the
  book held 7 names with ~196k CNY idle for one cycle until the next rebalance
  re-picked it. The skip was accidentally accretive (601857 fell ~12% that
  month). A live implementation must retry limit-cancelled entries; the
  backtest does not model that.
- **F4/F6/F7 (minor, wording)** — flat/halted overlap double-count fixed
  above; per-stock PnL disclosed as realized-only; "held continuously"
  corrected to selection-level continuity.
- **F5 (minor)** — one fill landed below the 20k CNY min-order floor after
  lot rounding (16.4k, Ping An, 2026-04-01). Cosmetic.
- **F8 (informational)** — the vendor-sampled valuation grid was frozen
  2026-11-10 with samples to that date; the ≤ as_of filter makes it
  code-safe, but retrospective vendor revision cannot be excluded offline.
  The hypothesis was formed knowing the window's bank leadership — disclosed
  in DESIGN.md.

## Why the Sharpe fell short

Volatility 14.1% annualized against a 3% risk-free floor: Sharpe 0.967 needs
either ≈+1pp more annual return or ≈0.4pp less volatility. The drag is
concentration in one factor cluster — four banks plus Ping An were held in
essentially every rebalance, so factor-level drawdowns (2026) flow straight
through. Diversifying the rank (e.g., sector caps) would be the obvious
*next hypothesis* — and is explicitly **out of scope here**: it would be a
new design requiring its own frozen gate and an uncontaminated window, not a
post-hoc patch on this one.

## Limitations (carried from DESIGN.md)

Static survivorship-bounded watchlist; qfq price approximation; long-only
cash account; vendor-sampled valuation series (≈12–18-day grid) carried
forward ≤21 calendar days; PE/PB reflect latest *published* reports, as a
live trader would see them; 2024–2026 leadership (banks/energy) was known in
hindsight — this study shows a *mechanical* value rank captures it, not that
anyone could have named it ex-ante. One observation of one factor on one
pool in one window is not proof of a durable premium.

## Reproduction

```bash
python research/value_factor_2026/prefetch_valuation.py   # one-time, network
python research/value_factor_2026/run_value.py --period smoke       # mechanics
python research/value_factor_2026/run_value.py --period evaluation  # the gate
python research/value_factor_2026/run_value.py --period evaluation --stress
```

Python ≥ 3.10, `pip install -e .`, frozen price inputs in
`data/regime_momentum/`. Runs assert against network access.
