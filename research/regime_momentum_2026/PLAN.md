# Regime-Momentum Research Plan (pre-registered)

Status: **pre-registration**, written before any candidate backtest was run.
Inputs are frozen; the gate below is fixed and will not be re-written after
results are seen. If the evidence does not clear it, the honest outcome is
"failed validation" — the same standard applied in
`research/sr_risk_budget_2026_09/results.json`.

## 1. Hypothesis

In A-shares, a **market-regime filter plus cross-sectional momentum** on a
liquid large/mid-cap pool should:

- H1: cut maximum drawdown materially versus buy-and-hold CSI 300, because the
  regime filter moves to cash during sustained index downtrends;
- H2: earn a higher Sharpe ratio than CSI 300 over the same window;
- H3: survive 2× commission and 0.3% slippage without turning negative
  (the edge is not a cost-free artifact).

Falsification: if the regime filter is the whole story, the `no_regime`
ablation should show similar drawdown. If momentum ranking adds nothing, the
`equal_weight_top_n` and ablations should be indistinguishable. Ablations are
run deliberately so a null result is *attributable*, not just reported.

## 2. Universe (survivorship mitigation)

`universe.py`: 44 names across 13 sectors, **including 10 names that lost 50%+
from their 2021-2022 highs** (LONGi, Ganfeng, Tianqi, WuXi AppTec, Shanghai
Airport, Air China, SAIC, Muyuan, CATL, Conch). Those are the names a momentum
strategy has to *dodge*; reporting must separate "PnL from winners" vs "PnL
from avoiding losers" (§7).

Limitation stated up front: this is still a hand-picked list of names that
existed and were liquid in 2022-2026. There is no point-in-time index
membership or ST ledger, so residual survivorship/selection bias cannot be
eliminated — only bounded and disclosed.

## 3. Data

- Source: eqlib disk cache warmed by `prefetch.py` (akshare, `qfq` adjusted).
- Window: **2022-01-04 .. 2026-10-27**, 1164 daily bars per name, 44/44 OK,
  benchmark `000300.XSHG` complete. `prefetch.py` coverage gate **PASSED**.
- Frozen to CSV snapshots under `data/regime_momentum/` (gitignored, sha256
  recorded in every result payload) by `freeze_inputs.py`.
- All runs are offline: the runner patches the public fetch functions to the
  frozen frames and asserts on any `requests` call. No downloads during
  evaluation, so the evidence is reproducible.
- 2022 is **warm-up only** (never scored): it supplies the 200-day regime MA
  and the momentum lookback before the first in-sample decision.

## 4. Chronological split (frozen, no re-cutting)

| Phase | Window | Use |
|---|---|---|
| warm-up | 2022-01-04 .. 2022-12-30 | indicator warm-up, never scored |
| development (IS) | 2023-01-03 .. 2024-12-31 | candidate comparison, **selection only** |
| validation (OOS-1) | 2025-01-01 .. 2025-12-31 | the gate; one shot per selected candidate |
| later_check (OOS-2) | 2026-01-01 .. 2026-10-27 | pristine confirmation, reported, never used to select or retune |

Each phase restarts from cash; yearly slices of a full-period run do not.

## 5. Pre-registered candidates

Seven hypotheses, several expected to fail. Parameters are round numbers chosen
from literature conventions (6-1 momentum, 200-day trend MA, 3×ATR trailing
stop), **not** fitted.

| id | change vs `base` | tests |
|---|---|---|
| `base` | 6-1 momentum (120d window, 20d skip), top 5, equal weight, weekly rebalance, regime = CSI300 > MA200 and MA200 non-declining over 20d | the core hypothesis |
| `no_regime` | regime filter disabled (always risk-on) | isolates H1: does the filter actually cut drawdown? |
| `breadth` | additionally require ≥50% of the pool above its own MA100 | cross-sectional confirmation vs index-only filter |
| `risk_adjusted` | rank by momentum / realized volatility instead of raw momentum | does vol-scaling the rank help? |
| `inverse_vol` | inverse-volatility position weights instead of equal | does sizing matter beyond selection? |
| `slow_10_1` | momentum window 200d (skip 20d) | horizon sensitivity |
| `monthly` | rebalance every 20 trading days | turnover/cost sensitivity |

Shared fixed risk layer for every candidate: 3×ATR(20) trailing stop that only
tightens, 120-day time exit, 5-day cooldown after a stop-out, max single-name
weight 22%, max gross exposure 95%, liquidity floor 1e8 CNY average 20-day
turnover, and a portfolio kill switch (−10% from high-water ⇒ flat for 20
sessions). Costs: `examples/_defaults.py` `DEFAULT_ORDER_COST` + 0.1% slippage.
Fills are at the next open; signals use completed bars only.

## 6. Selection rule and promotion gate (fixed now)

**Selection (development only).** Among candidates that satisfy all of:
- development max drawdown ≥ −25%,
- development completed round trips ≥ 3 per year,
- development total return > CSI 300 total return over the same window,

pick the **highest development Sharpe**. Ties break alphabetically. If no
candidate qualifies, the research stops here and is reported as a failure — no
rescue run, no new parameter sweep.

**Promotion gate (validation, one shot).** The selected candidate is promoted
only if all hold on 2025:
1. Sharpe ≥ 1.0,
2. total return > CSI 300 total return,
3. max drawdown less severe than CSI 300's over the same window,
4. completed round trips ≥ 3 per year,
5. stress run (2× commission, 0.3% slippage) still has positive total return.

**later_check** is executed once, after the gate decision, and is reported as
is. A negative later_check means "not promotable" — it is *not* an invitation to
retune. Reusing these windows for further tuning would not be a new
out-of-sample test and must be labelled as in-sample if it ever happens.

## 7. Attribution requirements

For the selected candidate, the report must show:
- yearly slices (2023, 2024, 2025, 2026) of return / Sharpe / max DD vs CSI 300;
- per-stock net PnL, split into `KNOWN_LOSERS` vs the rest, plus each loser's
  buy-and-hold return over the window — to state how much of the result is
  *avoidance* rather than selection;
- fraction of sessions flat (regime off / halted) and average gross exposure;
- exit-reason counts (stop, time, regime, rank-out);
- `eqlib.scientific.validate_backtest` output (bias, overfitting, statistics).

## 8. Known limitations to carry into the write-up

- Static 44-name watchlist; no point-in-time membership, ST, or delisting ledger.
- `qfq` normalized prices: fills use adjusted prices, so corporate actions and
  raw-price limit-up/limit-down behaviour are approximated, not modelled.
- No borrow, no shorting, no intraday signal; single-account cash strategy.
- Six years of A-share history covering one big bear and one policy-driven
  rally: regime results are conditional on that sample.
- Selecting on development Sharpe over 7 candidates is a multiple-testing
  problem; the validation gate is the correction, and it gets one shot.
