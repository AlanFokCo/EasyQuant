# Adversarial review record — value_factor_pit_2026

Reviewer: independent subagent, 2026-11-12. Scope: code, frozen data,
artifacts, protocol, and vendor risks. Verdict: **the gate pass survives the
audit; no critical or major findings.** Nine minor findings, dispositions
below.

| # | Finding (severity) | Disposition |
|---|---|---|
| M1 | Cancelled non-halt exits silently dropped until next rebalance (latent; occurred once, benign) | Disclosed in README Limitations; top robustness gap for any follow-on study |
| M2 | Runner source_sha256 in summaries ≠ shipped file (post-run cosmetic destination-path fix) | Verified behaviorally identical via git diff (same paths/guard; stress selections byte-identical to base); disclosed in README; lesson: re-commit immediately after any post-run edit |
| M3 | README "one insufficient-cash skip" understated: two cash-downsized partial fills (52% / 40% of target) | README corrected with exact figures and root cause (phantom sell proceeds from a suspended name; engine cash check enforced reality) |
| M4 | Amendment coverage numbers in mixed calibers (69 vs 57 vs 285) | DESIGN.md corrected to the reviewer's recomputed figures with caliber note |
| M5 | Ledger recorded smoke eligible "173–212" (first/last, not range; true range 156–232) | Ledger corrected |
| M6 | Reference docstring vs implementation nuance (byte-identical here due to BaoStock suspension padding) | Docstring corrected; caliber disclosed in README |
| M7 | Frozen history CSVs' inner code column lost zero-padding on resume re-write | Hashes self-consistent; filename keys drive all logic; results unaffected; disclosed; future refreezes must use dtype=str |
| M8 | Vendor-overlap correlation (0.9999999 index / 0.990 member) not preserved as artifact | README downgrades it to "indicative"; future probes must write their output to disk |
| M9 | Amendment participation premise static (150k → 267k by 2015) | README discloses; actual max fill 2.06% of daily volume — conclusion unaffected |

## Verified clean (reviewer's evidence, abridged)

- Amendment timeline: DESIGN frozen at commit 18e98f7 before any data existed;
  amendment committed 02:07:50; first backtest 02:09:43; the runner
  hard-requires the sha256 manifest — no pre-amendment run was possible.
  Gate criteria/windows never edited post-freeze.
- Selection integrity: all 72 rebalances independently re-derived from raw
  membership + history CSVs — picks, scores, eligible counts match exactly;
  no pick predates membership; index_removal exits all match real removals;
  churn clusters on official CSI300 review dates.
- Fills: 203/203 validation fills at next-open × (1±0.001) exactly (stress
  ±0.003); lot-rounded; stamp duty + commissions to the cent; no fills on
  zero-volume days or within 9.8% of limits.
- Gate metrics reproduce to full precision from equity.csv + frozen benchmark;
  equity curve independently rebuilt from trades (max deviation 0.073 CNY);
  realized 995.8k + unrealized 330.4k reconciles with total profit.
- Kill switch: 7 halts × exactly 20 sessions; per-halt recorded drawdown
  matches high-water-reset recomputation; no position survived a halt
  (600649's suspended exit was resubmitted daily 17× and filled at
  resumption).
- Reference: +80.43% / −43.79% reproduces exactly; delisting-aware.

## Reviewer's strongest remaining caveats (endorsed)

1. Regime concentration: 2014 alone supplied +92.91%; final book 8/8 banks.
   The gate proves "cheap CSI300 names, 2013–2015" — not a durable premium.
2. Floor sensitivity untested: 3 validation picks in the [2e7, 3e7) turnover
   band contributed ≈8% of PnL.
3. Single vendor (BaoStock) for membership and valuations.
