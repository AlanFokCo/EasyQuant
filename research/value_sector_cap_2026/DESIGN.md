# value_sector_cap 2026 — Design (frozen before any run)

Written 2026-11-10, before any run of this strategy. Fifth frozen-design
study on the pool; a direct follow-up to `research/value_factor_2026` (gate
3/4, Sharpe 0.967 vs the frozen 1.0 bar, attribution: concentration in the
bank/insurance factor cluster).

## Contamination protocol (the important part)

This hypothesis was formed **after** seeing value_factor's 2024–2026 results,
so 2024–2026 can never gate this design. The protocol therefore moves the
gate to windows never scored by any *factor* study in this project.
Correction (added after adversarial review): the claim was originally written
as "never scored by any study", which is **false** —
`research/sr_risk_budget_2026_09` scored 11 technical-entry candidates on
2020-01-01..2022-12-31 (an 8-name subset of this pool), so 2021–2022's
benchmark behaviour was known in-project. Mitigants: the hypothesis descends
from value_factor's 2024–2026 attribution, not from that technical study;
the known bear market makes gate criteria 2–4 harder, not easier; and the
gate failed anyway. But a sixth study must treat 2021–2022 as scored:

| phase | window | use |
|---|---|---|
| warm-up | 2015-01-01 .. 2015-12-31 | indicator/factor warm-up only, never scored |
| development | 2016-01-01 .. 2020-12-31 | scored; design iteration allowed here |
| **validation (the gate)** | **2021-01-01 .. 2022-12-31** | **one shot**, plus stress |
| later_check | 2024-01-01 .. 2026-10-27 | reported, explicitly labelled in-sample-informed (contaminated by value_factor's known result) |

2023 is deliberately unused: it served as value_factor's smoke window and its
headline metrics are known. The 2021–2022 gate years combine a value-hostile
tape (2021 growth peak) with a value-friendly bear (2022) — a harder, more
informative test than a single regime.

Price data is a NEW freeze (`data/value_pool_prices/`, 2015-01..2026-10) —
the prior freeze (`data/regime_momentum/`, 2022-01..2026-10) is untouched so
old evidence hashes stay valid. qfq anchors shift between download dates;
the later_check comparison to value_factor's run is therefore approximate at
the level of a few corporate actions, which is one more reason it is not a
gate.

## Hypothesis

Adding a **sector cap** to the value rank diversifies the factor cluster
(banks/insurance held ~62.5% of the book in value_factor) without giving up
the value premium: higher Sharpe than value_factor on the same window, with
the same drawdown discipline.

## Frozen choices

Everything identical to `value_factor_2026` unless listed:

- Same universe (44 names, 13 sectors, `UNIVERSE_BY_SECTOR`), same
  eligibility (PE>0, PB>0, fresh ≤21d valuation, price ≥3, turnover ≥1e8),
  same score (0.5×PE pct-rank + 0.5×PB pct-rank, ascending), top 8,
  rebalance-time equal weights (caps 15%/95% order-time, drift-tolerant),
  monthly cadence, same costs and stress definition, cash 1,000,000,
  benchmark CSI 300. ~~kill switch −10%/20 sessions~~ — REMOVED in v2 after
  development evidence (see Iteration history below); the kill switch was
  inherited from the prior studies and proved harmful on a fully-invested
  factor book.
- **CHANGE 1 — sector cap**: at most **2** names per sector at each rebalance;
  the cheap-first walk skips names whose sector is full.
- **CHANGE 2 — entry retry (execution realism, review finding F1 of the prior
  study)**: entry orders are tracked; an entry cancelled unfilled (e.g.,
  limit-up open) is resubmitted **once** at the next session; if that fails
  too, the name waits for the next rebalance (no chasing limit-up streaks).
- **CHANGE 3 — halt-exit resubmission (review finding F3)**: while halted,
  every surviving position always has an open exit order.
- Late-IPO names (e.g., CATL 2018-06) become eligible when they have
  sufficient history, a fresh valuation sample, and pass filters — the pool
  is static, membership is data-driven. Disclosed as survivorship-bounded.

## Gate (declared pre-run, on the 2021–2022 validation window)

1. total return > CSI 300 over the same window,
2. max drawdown ≥ −25%,
3. Sharpe ≥ 1.0,
4. stress run (2× commission, 0.3% slippage) total return > 0.

All four or the study is a reported failure. Development-window results may
be inspected freely (that is what the window is for); validation gets one
shot; later_check is reported as-is and never used to retune.

## Iteration history (development window, 2016–2020 — disclosed)

- **v1 (as first written: sector cap + entry retry + inherited kill switch)**:
  dev +42.3% vs CSI300 +39.7%, max DD **−51.4%**, Sharpe 0.30, 10–11 halts
  (90 halt exits, 214 halted sessions). Failure mode: after each −10% trigger
  the resume logic resets high water, so the kill switch is not a drawdown
  cap but a **loss crystallizer** — it laddered seven ~−10% crystallizations
  and re-entered into further losses (2018, 2020). In the prior fully-technical
  studies it fired rarely and looked benign; on a fully-invested factor book
  it is actively harmful.
- **v2 (kill switch removed; everything else unchanged)**: dev +92.7% vs
  +39.7%, max DD −39.4%, Sharpe 0.52. Yearly: 2016 +11.4% (idx −11.3%),
  2017 +68.3% (+21.8%), 2018 −13.6% (−25.3%), 2019 +17.6% (+36.1%),
  2020 +1.2% (+27.2%). Reading: the value factor wins big in value regimes
  and bleeds in growth-momentum regimes; nothing in the no-timing-machinery
  scope can fix that, and exposure scaling cannot move Sharpe.
- **Selection rule for the validation shot** (declared after development
  iteration, before any validation run): the iterated variant proceeds if its
  development total return beats CSI300's. v2 qualifies (+53pp excess).
  **v2 is frozen for validation.** The deep factor drawdowns make gate
  criteria 2 and 3 genuinely uncertain — that is what the validation window
  is for.

## Known limitations

All of value_factor_2026's, plus: the 2016–2020 development window predates
ChiNext's 20% daily limit regime change (2020-08) — engine price-limit rules
are board/date-aware; sector labels are today's labels applied historically
(a name's 2016 business mix may differ); the hypothesis carries hindsight
about the *factor* working in 2024–2026 — the gate window mitigates but does
not erase that.
