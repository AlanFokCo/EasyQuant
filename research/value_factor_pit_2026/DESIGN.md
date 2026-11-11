# value_factor_pit 2026 — Design and go/no-go protocol

Written 2026-11-11 before implementation. This is the sixth frozen-design
study. It does **not** introduce a new signal or tune a parameter. Its purpose
is to test the central unresolved weakness of `value_factor_2026`: the static,
hindsight-selected 44-name pool.

## Go/no-go data gate

The study proceeds only if BaoStock provides, for the full 2009–2015 input
window:

- CSI 300 membership on an arbitrary historical date (`query_hs300_stocks`),
  including names no longer in the index;
- daily OHLCV, `peTTM`, `pbMRQ`, `tradestatus`, and `isST` for current and
  delisted names;
- sufficient valuation coverage to admit at least 100 eligible names on the
  first development rebalance and at least 150 on every gate rebalance.

The source is validated by overlap against the existing akshare freeze for
2022–2026, checking that prices are the same series up to adjustment-anchor
scaling and that PE/PB coverage is daily rather than vendor-sampled. If this
gate fails, the study stops and reports the data limitation; there is no
fallback to today's constituents or a static pool.

## Frozen strategy choices

Identical economics to `value_factor_2026`:

- monthly rebalance every 20 trading days;
- eligibility: profitable PE(TTM) > 0, PB(MRQ) > 0, close ≥ 3 CNY, 20-day
  average turnover ≥ 1e8 CNY, normal trading status, non-ST on the decision
  day, and a member of CSI 300 on that decision day;
- score: `0.5 × percentile_rank(PE ascending) + 0.5 × percentile_rank(PB
  ascending)`;
- cheapest 8 names, rebalance-time equal-weight targets with 15% single-name
  and 95% gross order-time caps; winners are not trimmed between rebalances;
- exits on rank-out or loss of membership; one entry retry after an unfilled
  cancelled order, then wait for the next rebalance;
- kill switch −10% from high water ⇒ flat 20 sessions, retained to match the
  original value_factor study (not the sector-cap variant);
- 1,000,000 CNY initial cash, CSI 300 price benchmark;
- costs from `examples/_defaults.py`, 0.1% slippage; stress at 2× commission
  and 0.3% slippage;
- completed bars only, next-open fills, no network during evaluation.

The only substantive change is the universe: point-in-time CSI 300 membership
at each rebalance, with daily point-in-time valuation and status fields. The
non-ST and normal-trading requirements become measurable for the first time
and are therefore part of eligibility, rather than an unverified disclaimer.

## Windows

| phase | window | use |
|---|---|---|
| warm-up | 2009-01-01 .. 2009-12-31 | turnover history only |
| smoke | 2012-01-01 .. 2012-12-31 | mechanics only, inside development |
| development | 2010-01-01 .. 2012-12-31 | scored once for data/pipeline validation, not parameter search |
| **validation (gate)** | **2013-01-01 .. 2015-12-31** | **one shot**, plus stress |

No post-2015 window is needed for the gate. Existing 2016–2026 factor results
are reported only as already-contaminated context, not rerun for selection.

## Pre-run amendment (2026-11-12, before any backtest on these windows)

The first coverage check failed: the `min_avg_turnover = 1e8 CNY` floor —
copied from the 2022–2026 pool studies — excluded up to 80% of CSI300 members
in mid-2014 (only 69/300 passed on 2014-06-06), while PE/PB and status
coverage were fine (285/300). That absolute floor is a miscalibration of the
execution-feasibility filter across eras, not part of the alpha hypothesis.

Amended rule: `min_avg_turnover = 2e7 CNY`, derived from position size, not
from window statistics: the largest position is 15% × 1,000,000 = 150k CNY,
which is 0.75% participation of a 2e7 CNY/day name — already conservative.
This change was made before any backtest run on the PIT windows, observed only
the liquidity distribution (not returns), and is disclosed here and in the
ledger. Re-checked coverage with the amended floor: development min 156
eligible, gate min 189, gate median 221 — the data gate now passes.

## Gate

On the 2013–2015 validation window:

1. total return > CSI 300 total return;
2. max drawdown ≥ −25%;
3. Sharpe ≥ 1.0;
4. stress total return > 0.

All four or the study is a reported failure. The point-in-time equal-weight
universe return is reported alongside as a diagnostic reference; it is not a
tradable portfolio at 1,000,000 CNY and is not a gate criterion.

## Required attribution

- yearly return/Sharpe/max drawdown versus CSI 300;
- point-in-time equal-weight universe return over the same dates;
- membership churn, number of eligible names, exits due to index removal;
- performance on names later removed from the index versus continuing members;
- per-stock realized PnL and open-position disclosure;
- valuation coverage, ST/suspension exclusions, failed entries and costs.

## Limitations to carry forward

BaoStock is a secondary vendor; adjustment conventions and fundamental
restatements can differ from other vendors. Historical index membership is
sampled on rebalance dates, so between-date changes are handled at the next
rebalance, not on the official effective date unless it coincides. Equal-weight
universe diagnostics are frictionless and not directly investable at this cash
level. A 2013–2015 gate contains the 2015 bubble and crash; it is one regime
sequence, not universal proof.
