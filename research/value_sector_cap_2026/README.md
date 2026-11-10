# value_sector_cap 2026 — Outcome: FAILED the 2021–2022 validation gate (1/4)

**Verdict (gate and protocol frozen in DESIGN.md): the sector-capped value
factor passed 1 of 4 criteria on the clean validation window and is a
reported failure.** The hypothesis it tested — "sector caps lift the value
factor's Sharpe above 1.0" — did not survive contact with unseen data.

| gate criterion (validation 2021–2022) | required | observed | pass |
|---|---|---|---|
| total return vs CSI 300 | > −25.71% | **−0.40%** (+25.3pp excess) | ✓ |
| max drawdown | ≥ −25% | **−28.33%** (CSI 300: −39.59%) | ✗ |
| Sharpe | ≥ 1.0 | **−0.05** | ✗ |
| stress (2× comm, 0.3% slip) | > 0 | **−2.15%** | ✗ |

Validation yearly slices: 2021 +8.13% (idx −5.20%, Sharpe 0.34),
2022 −7.89% (idx −21.63%, Sharpe −0.42). Two bear years, two relative wins,
zero absolute return: the factor did its defensive job and nothing more.

## Why this window and not 2024–2026 (contamination protocol)

The hypothesis was formed *after* seeing value_factor's 2024–2026 result
(gate 3/4, Sharpe 0.967, attribution: bank-cluster concentration), so
2024–2026 cannot test it. The gate ran on 2021–2022, with 2016–2020 as the
iterable development window (new price freeze `data/value_pool_prices/`,
2015–2026; the 2022 freeze is untouched so old evidence hashes stay valid).
later_check on 2024–2026 is reported below, labelled in-sample-informed.

**Correction (adversarial review, Major 1):** an earlier draft claimed
2021–2022 was "never scored by any study in this project" — false.
`research/sr_risk_budget_2026_09` scored 11 technical-entry candidates on
2020–2022 (8-name subset of this pool), so the gate window's benchmark
behaviour was known in-project. Mitigants: this hypothesis descends from
value_factor's 2024–2026 attribution, not from that technical study; the
known bear market made gate criteria 2–4 harder, not easier; the gate failed
anyway. Precise claim: 2021–2022 was never scored by any *factor* study. Any
sixth study must treat it as scored.

## Iteration history (development 2016–2020, disclosed in DESIGN.md)

- **v1** (sector cap + entry retry + inherited kill switch): +42.3% vs
  +39.7%, max DD **−51.4%**, Sharpe 0.30. Failure mode found: the inherited
  kill switch resets high water on resume, so it is not a drawdown cap but a
  **loss crystallizer** — ~7 consecutive −10% crystallizations with
  re-entries into further losses (10–11 halts, 214 halted sessions). On a
  fully-invested factor book it is actively harmful; in the prior
  barely-invested technical studies it looked benign.
- **v2 = the frozen validated design** (kill switch removed, nothing else
  changed): dev +92.7% vs +39.7%, DD −39.4%, Sharpe 0.52. Yearly: 2016
  +11.4% (idx −11.3%), 2017 +68.3% (+21.8%), 2018 −13.6% (−25.3%), 2019
  +17.6% (+36.1%), 2020 +1.2% (+27.2%). The factor wins big in value
  regimes and bleeds in growth-momentum regimes; no in-scope change moves
  Sharpe to 1.0 — the validation window existed to test whether the
  2021–2022 regime was kind enough anyway. It was not.

## What the sector cap did (attribution, validation window)

Mechanically it worked as designed: picks spread across 8 sectors
(materials 49 pick-slots, banks capped at 2 names = 46, transport 30, auto
25, energy 22, insurance 17, tech 10, utilities 1) instead of the uncapped
study's bank/insurance majority. Winners were cyclical value: Baosteel
+91.9k, Shenhua +48.9k, SIPG +32.2k, Daqin +20.6k; losers: Ping An −30.3k,
BOE −19.1k, ICBC −15.9k, PetroChina −13.8k. known_loser_pnl = 0 (none were
picked — the profitability screen did that). Activity: 25 round trips,
25 rebalances, costs 3,276 CNY (0.33pp), 94.3% average exposure.

## later_check 2024–2026 (in-sample-informed; NOT evidence)

Run once, reported as-is, never used for selection: **+48.88% vs CSI300
+18.02%, Sharpe 0.80, max DD −14.64%, win rate 73.9%.** Versus the uncapped
value_factor on the same window (+54.55%, 0.967, −14.79%): the sector cap
*cost* 5.7pp of return and 0.16 Sharpe even in the window that motivated it —
bank concentration was the feature there, not the bug. New freeze qfq anchors
differ from the 2022 freeze by a few corporate actions; comparison
approximate at that level.

## Adversarial review (independent subagent, 2026-11-10/11)

Reviewed against frozen inputs and artifacts; independently re-derived **all
120 rebalances** across the validation/development/later_check runs from the
raw valuation and price CSVs — every pick, score, and weight matched; all 715
fills verified as next-day open × (1±slippage); 0 sector-cap violations in
156 rebalances; no look-ahead in price or valuation paths (worst valuation
staleness 17d ≤ 21d cap). Three-axis verdict: accuracy PASS, feasibility
PASS (worst fill participation 0.41% of daily turnover), soundness PASS
except as noted.

Findings and dispositions:

- **Major 1 — the window-novelty claim was false.** Corrected above and in
  DESIGN.md.
- **Minor — dev-v2 → validated-code equivalence rests on recorded configs,
  not git history.** The directory was untracked between the dev-v2 run and
  the validation freeze; recorded configs and runner hash show the only diff
  was the `use_kill_switch` default flip, but the exact diff is unrecoverable.
  Lesson adopted: commit each frozen code state at freeze time (this study's
  first commit now includes the validated file).
- **Minor — the entry-retry machinery (CHANGE 2) never fired in any run**
  (0 `entry_retry` events; validation 42/42 entries filled at first attempt).
  It is untested code in the critical path, correct by inspection only.
- **Minor — benchmark caliber asymmetry (inherited harness)**: the benchmark
  return includes the window's first-day move while the strategy is all-cash
  on day 1. In development that day was the 2016-01-04 circuit breaker
  (−7.02%), so dev excess is ~+42.5pp rather than "+53pp"; in validation the
  asymmetry worked *against* the strategy (day 1 +1.08%). Decision-neutral in
  both windows and consistent across all five studies.
- **Minor — reproduction note**: the immutable-evidence guard means the
  commands below only run on a fresh `reports/` tree (or with a new
  `--label`); development artifacts correspond to the code states whose
  sha256 are recorded inside each summary.json.

## Standing conclusion across the five studies

Technical entries (breakout-retest, regime momentum, support pullback): no
edge after costs. Value factor: real relative edge (+25pp/2yr validation,
+36.5pp/2.8yr on the known-contaminated 2024–2026 window) but its absolute
quality is regime-dependent — Sharpe cleared 1.0 in exactly one of the seven
scored years (2017 dev). **The honest summary for this pool: value is a
beta-dampener with a regime-conditional premium, not a Sharpe-1
strategy.** Diversifying the factor's sector bets did not change that.

## Reproduction

```bash
python research/value_sector_cap_2026/prefetch_prices.py   # one-time, network
python research/value_sector_cap_2026/run_capped.py --period smoke
python research/value_sector_cap_2026/run_capped.py --period development
python research/value_sector_cap_2026/run_capped.py --period validation   # gate
python research/value_sector_cap_2026/run_capped.py --period validation --stress
python research/value_sector_cap_2026/run_capped.py --period later_check  # labelled
```

Python ≥ 3.10, `pip install -e .`, valuation inputs `data/value_factor/`,
price inputs `data/value_pool_prices/`. Runs assert against network access.
