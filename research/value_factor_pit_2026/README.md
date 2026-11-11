# value_factor_pit 2026 — Gate: PASSED (4/4) on 2013–2015

**Verdict (gate frozen in DESIGN.md before any run on these windows): the
point-in-time value factor passed all four criteria on the clean 2013–2015
validation window — the first study in this research line to do so.**

| gate criterion (validation 2013–2015) | required | observed | pass |
|---|---|---|---|
| total return vs CSI 300 | > +47.88% | **+132.58%** (+84.7pp excess) | ✓ |
| max drawdown | ≥ −25% | **−23.90%** (CSI 300: −43.48%) | ✓ |
| Sharpe | ≥ 1.0 | **1.115** | ✓ |
| stress (2× comm, 0.3% slip) | > 0 | **+125.03%** (Sharpe 1.072) | ✓ |

- Design, go/no-go data gate and pre-run amendment: `DESIGN.md`
- Implementation plan and execution ledger: `IMPLEMENTATION_PLAN.md`
- Evidence: `reports/value_factor_pit/{smoke,development,validation}/`
  (summary.json with data manifest sha256, equity/trades/events CSVs,
  selections.json)
- Frozen inputs: `data/value_factor_pit/` (BaoStock, 662 files, sha256
  manifest; 2009–2015 prices + daily PE(TTM)/PB(MRQ)/status + CSI300
  membership at every rebalance date)

## What this study changed — and what it did not

The factor is byte-for-byte the one from `value_factor_2026` (0.5×PE-rank +
0.5×PB-rank, cheapest 8, monthly rebalance, 15%/95% order-time caps, −10%/20d
kill switch, same costs). What changed is the **universe and data quality**:

- static 44-name hindsight pool → **point-in-time CSI300 membership** at each
  rebalance (300 names per date, removed members included while they were
  members — including delisted names like 600005);
- vendor-sampled PE/PB carried forward ≤21 days → **daily** PE(TTM)/PB(MRQ);
- unverifiable ST/suspension caveats → daily `tradestatus`/`is_st` filters;
- liquidity floor amended pre-run from 1e8 (a 2020s-calibrated absolute) to
  2e7 CNY (0.75% participation at the 150k max position) — the amendment and
  its evidence are in DESIGN.md.

## Decomposition: factor vs pool vs index (2013–2015)

| series | total return | max DD |
|---|---|---|
| **value factor (this strategy)** | **+132.58%** | −23.90% |
| PIT equal-weight universe (frictionless diagnostic) | +80.43% | −43.79% |
| CSI 300 index | +47.88% | −43.48% |

The pool itself beat the cap-weighted index (+80.4% vs +47.9% — equal-weight
tilt), and the value selection beat its own pool by a further +52pp. The
factor effect is real relative to both baselines; it is not an artifact of the
pool.

Yearly slices (continuous run, re-based):

| year | strategy | CSI 300 | strategy DD | CSI 300 DD | strategy Sharpe |
|---|---|---|---|---|---|
| 2013 | +3.06% | −7.65% | −18.12% | −22.16% | 0.10 |
| 2014 | **+92.91%** | +51.66% | −13.35% | −10.12% | 2.56 |
| 2015 | +16.99% | +5.58% | −20.32% | −43.48% | 0.57 |

2014 supplied most of the excess (the great low-valuation rally); 2015 shows
the drawdown control through the bubble crash (−20.3% vs −43.5%).

## Attribution and execution (validation window)

- 30 rebalances, 93 round trips (31.2/yr), costs 15.2k CNY (1.5pp); win rate
  55.9%. 110/110 entry orders filled at first attempt — the entry-retry path
  existed but was never needed.
- Eligible names per rebalance: min 189, median 221, max 271 of 300.
- Most-held names: 600000 浦发 (29/30 rebalances), 600015 华夏, 601166 兴业,
  600036 招商, 000001 平安 — the cheap-bank cohort, now selected from the
  full index rather than a hand-picked pool.
- Top realized PnL: 浦发 +188.7k, 民生 +171.4k, 平安银行 +110.1k,
  中信 +105.6k, 招商 +72.5k. Largest losses: 建行 −32.2k, 交行 −25.7k.
- Exit reasons: rank_out 36, portfolio_halt 73, index_removal 2.
- The kill switch fired 7 times (140 halted sessions): it hurt in the
  development bear (2010–2012: −4.6% vs −29.4% but DD −31.8%) and still left
  the validation gate passed; its net effect is mixed, reported as-is.

## What this does and does not establish

**Established:** on point-in-time CSI300 membership with daily fundamentals,
a mechanical cheapness rank had genuine, cost-robust excess return over both
the index and its own universe in 2013–2015, with materially smaller
drawdowns than either baseline.

**Not established:** durability after 2015 (the 2016–2026 windows are
contaminated by prior studies and were not rerun here); capacity beyond
~150k CNY positions; vendor independence (single-source BaoStock);
independence from the known bank-heavy value regimes of 2014. One clean gate
pass after five honest failures is evidence, not proof.

## Limitations

BaoStock is a secondary vendor (adjustment/restatement conventions differ
from akshare — overlap correlation vs the akshare freeze: 0.9999999 on CSI300
daily returns, 0.990 on a spot-checked member); membership is sampled at
rebalance dates only; the equal-weight reference is frictionless and not
investable at 1M CNY; qfq-based price-limit checks and next-open fills are
approximations disclosed in prior studies; entry sizing estimates use signal
closes, actual fills gap (one "insufficient cash" skip observed).

## Reproduction

```bash
python research/value_factor_pit_2026/baostock_freeze.py   # one-time, network
python research/value_factor_pit_2026/run_pit_value.py --period smoke
python research/value_factor_pit_2026/run_pit_value.py --period development
python research/value_factor_pit_2026/run_pit_value.py --period validation
python research/value_factor_pit_2026/run_pit_value.py --period validation --stress
```

Python ≥ 3.10, `pip install -e .` plus `baostock`. Runs assert against
network access; unit tests: `python -m pytest research/value_factor_pit_2026/tests/`.
