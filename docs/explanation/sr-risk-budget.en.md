# Support/resistance with a risk budget

`sr_risk_budget` is a fixed-parameter, long-only daily research strategy for Shanghai/Shenzhen main-board A-shares. Run `examples/25_sr_risk_budget.py`. It reuses ATR and historical range calculations from the existing support/resistance module, with independent daily risk and order management; it does not replace `ashare_sr_leader`.

**Sustained profitability has not been established.** Risk parameters are planning constraints, not return promises or hard loss limits. Passing tests establishes only the behaviors covered by those tests.

## Trading rules

1. New entries require CSI 300 above its 120-day moving average, with that average above its value 20 sessions earlier. A failed filter or missing benchmark data requests liquidation.
2. Stocks must close above a non-declining 60-day average, above their open and previous close. Estimated trailing 20-day turnover must reach CNY 50 million; ATR/price must not exceed 6%. Turnover uses `close × volume`; volume must be in **shares**.
3. Enter either a rebound near the previous 60-day low or a retest of resistance following a volume-confirmed breakout within the previous five sessions. Retest resistance is frozen before the breakout window. No future or centered pivot confirmation is used.
4. The initial stop is the lower of support minus 0.5 ATR and the buy limit minus 1.5 ATR. Planned stop distance must be 1.5%–8% of the limit price.
5. Support rebounds target 0.3 ATR below prior resistance. Breakout retests consider historical overhead resistance from before the breakout; absent that, the target is an explicitly **projected** 3R level. Reject reward/risk below 1.8.
6. Stops only tighten: peak closing price since entry minus 3 ATR. A close through the stop, a target reached, or 40 sessions held requests an exit. Wait five sessions after a completed exit before considering the same stock again.

## Position sizing and portfolio protection

| Parameter | Default | Meaning |
|---|---:|---|
| `risk_per_trade` | 0.5% | Planned risk per entry, including friction allowances |
| `max_open_risk` | 2% | Existing and pending-entry risk budget when opening positions |
| `max_stock_weight` | 15% | Single-stock entry value cap |
| `max_exposure` | 60% | Gross equity exposure cap when opening positions |
| `max_positions` | 5 | Maximum holdings |
| `volume_participation` | 0.5% | Buy quantity relative to trailing 20-day average shares traded |
| `halt_drawdown` | 10% | Request liquidation after this decline from the risk episode's equity peak |
| `halt_days` | 20 | Minimum sessions before resuming, also requiring a flat portfolio and a recovered market filter |

Quantity is the minimum permitted by risk, cash, single-stock value, portfolio exposure and historical liquidity, rounded down to 100 shares. Minimum commissions are reserved. Pending liquidations continue to consume exposure and risk; no new positions are opened while exits remain outstanding.

Price changes can move actual weights above entry caps. The strategy does not mechanically rebalance every day to fixed percentages. Resuming after a halt resets the next risk episode's peak, **not the cumulative report equity or maximum drawdown**.

## Signal and execution timing

Use only the daily `after_trading_end` callback. After 15:00, combine the strictly prior-day history from `attribute_history` with today's completed `data[code]` bar. Do not move this callback to the morning.

- A signal formed at the close on T can first fill at the open on T+1.
- A buy limit approximately 0.5% above the signal close prevents chasing gaps up; the slippage-adjusted fill must also satisfy the limit.
- Entry orders attempt only the next open. Cancel unfilled remainders at that session's close, tracking only actual partial fills.
- Stops and targets are **closing signals**, not guaranteed intraday stop orders. Same-day resale of a new purchase is prohibited. Limit-down moves, suspensions and gaps can create losses beyond the planned budget.
- Cancelled exits are resubmitted at a later close while the exit intent remains active. Partial exits retain their remaining quantity.

## Running and input data

From the repository root:

```bash
pip install -e ".[dev]"
python examples/25_sr_risk_budget.py --download --start 2021-01-01 --end 2025-12-31
python examples/25_sr_risk_budget.py --stress --start 2021-01-01 --end 2025-12-31
```

`--download` fetches and overwrites snapshots in `data/sr_risk_budget/`. Omit it for repeat evaluations against unchanged inputs. The default eight-stock universe comes directly from `examples/_defaults.py`: it is a selected watchlist, not point-in-time index membership.

To supply existing CSVs:

```bash
python examples/25_sr_risk_budget.py --data-dir /path/to/snapshots --stress
```

Files are named `<code>_daily_qfq.csv`, including `000300.XSHG_daily_qfq.csv`. The first column is a date index. Required columns are `open,high,low,close,volume`, with consistently forward-adjusted CNY prices and stock volume in shares. `--download` multiplies eqlib main-board stock volumes by 100 to convert lots to shares; supplied CSVs are already in shares and are not converted again. Index volume retains its source units and is not used for liquidity calculations. Cover the final test session and provide at least `config.history_bars` valid warm-up bars (140 by default) before the start. Duplicate/unordered dates, nonfinite values, invalid OHLC, missing benchmark sessions or truncated coverage cause errors instead of silently shortening the evaluation. Missing stock sessions are recorded in the manifest, without inventing fills.

Offline runs use the packaged calendar and bind engine/report reads to the same immutable CSV frames, preventing a later download of different benchmark data. This example adapter is scoped to the Python process; do not run it concurrently in multiple threads.

Default commissions are 0.025% with a CNY 5 minimum, matching the shared examples. The engine applies date-aware sell stamp duty. Base one-way slippage is 0.1%; `--stress` reruns with twice the commission rates/minimum and 0.3% one-way slippage. See the [tax authority's announcement](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) for the stamp-duty reduction's effective date.

Outputs under `reports/sr_risk_budget/`:

| File | Purpose |
|---|---|
| `summary.json` | Fixed parameters, costs, input SHA-256 hashes, full-period/yearly metrics, cost stress results |
| `equity.csv` | Daily equity, cash, exposure and halt state |
| `trades.csv` | Actual engine fills and fees |
| `events.csv` | Buy limits, support, stops, targets, exit reasons, halt/resume events |

Calendar-year metrics slice one continuous position path and retain the prior equity observation at each boundary. They do not restart from cash each year and are not independent or certified untouched out-of-sample tests. A single example run does not perform a parameter search. Do not select only winning years to claim stable profits.

Use `--synthetic` when validating artificial data; reports are labeled execution tests, not historical return evidence.

## Reuse

```python
from eqlib import run_backtest
from eqlib.strategies import SRRiskConfig, make_sr_risk_budget_strategy

initialize = make_sr_risk_budget_strategy(
    ["601398", "601318", "600276", "601088"],
    config=SRRiskConfig(),
)
result = run_backtest(initialize, "2023-01-01", "2025-12-31", starting_cash=1_000_000)
```

Supply `eligible(code, date)` for point-in-time universe/ST eligibility and exit requests when membership is lost. Without it, the universe is explicitly static. Today's names or ST flags must not be treated as historical facts. The API is **EXPERIMENTAL**, for main-board daily research only, without a live-broker adapter.

## Validation boundaries

Regressions cover support bounces, breakout retests, future-data changes leaving earlier signals unaffected, fees/lots, simultaneous reservations, next-open fills, partial fills, gaps through stops, limit-down exit retries, halt recovery and CSV truncation. Synthetic prices validate these behaviors, not profitability.

Inherited research approximations remain: execution at forward-adjusted prices, daily-volume fill caps, estimated board limits, no complete historical ST/delisting inventory, no opening-auction queue and no corporate-action cash/share ledger. These backtests cannot guarantee stable profits or establish readiness for live trading.

Before making performance claims, freeze parameters and point-in-time membership, evaluate new data not used in design, report net returns, drawdowns, completed trades, market regimes and friction stress, and then paper trade. Preserve failed evaluations whenever a target is missed.

Trading-rule references: [current SSE trading rules](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml), [SSE round/odd-lot guidance](https://www.sse.com.cn/lawandrules/guide/stock/jyglywznylc/tz/c/c_20230209_5716007.shtml), and [HKEX Stock Connect FAQ](https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Getting-Started/Information-Booklet-and-FAQ/FAQ/FAQ_Cn.pdf).

## Optional breakout rules and September 2026 research record

`SRRiskConfig()` preserves the original behavior. Three strictly boolean experimental switches are available:

| Parameter | Default | Behavior |
|---|---|---|
| `allow_breakout` | `False` | If neither a support bounce nor retest triggers, permit a direct breakout above prior `level_window` highs |
| `require_market_slope` | `True` | `False` removes only benchmark slope confirmation; price must still close above its average |
| `exit_on_market_filter` | `True` | `False` removes forced market-filter exits; entry filtering, stock stops, time/eligibility exits and portfolio halts remain active |

Direct breakouts use a historical high **excluding the signal bar**. The close must exceed it by 0.1 ATR but no more than 1.5 ATR, with volume at least the prior 20-session average. Existing stops, reward/risk checks, friction reservations and next-open limits apply. Overhead uses only prior data; absent overhead, the 3R target is projected. The feature stays off by default because validation failed.

```bash
python examples/25_sr_risk_budget.py --allow-breakout --stress \
  --start 2020-01-01 --end 2026-09-10 \
  --data-dir /path/to/frozen-inputs --output reports/sr_breakout
```

On the fixed eight-stock history, baseline averaged **2.34%** exposure and completed 26 round trips with six winners. No support bounce satisfied the combined prior-60-day-low proximity and non-declining 60-day-average conditions. Only 38 breakout-retest candidates remained. This explains sparse trading and idle cash; more signals alone do not establish an edge.

Three rounds tested **11 configurations including baseline**, declaring each round first. Development covers 2020–2022, validation 2023–2024. Each starts independently with CNY 1 million and prior warm-up data. Later rounds used validation feedback, introducing repeated-selection bias. All results are retained:

| Candidate | Development net return | Validation net return | Validation max drawdown |
|---|---:|---:|---:|
| `baseline` | -0.76% | -1.30% | 1.78% |
| `short_levels` | +1.32% | -1.30% | 2.10% |
| `breakout` | +7.34% | -0.78% | 2.19% |
| `trend_exit` | +0.84% | -0.30% | 1.80% |
| `early_market` | +7.27% | -5.19% | 6.04% |
| `long_trend` | +6.84% | -4.90% | 5.98% |
| `early_trend_exit` | +0.28% | -1.56% | 2.74% |
| `channel60` | +7.97% | -0.49% | 1.44% |
| `stock_exits` | +8.17% | -1.05% | 3.28% |
| `channel60_stock_exits` | +8.80% | -1.46% | 3.21% |
| `patient_exits` | +8.02% | -0.67% | 2.19% |

The declared gate required positive returns and drawdown below 12% in both periods, more fills than baseline, then doubled commissions and 0.3% slippage. **No configuration passed the return gates; none was selected for promotion.** `channel60`, equivalent to `SRRiskConfig(allow_breakout=True)`, was frozen before the later check only as a minimal-change comparison. Positive full-period returns did not change the gate.

| Check | Baseline | `channel60` |
|---|---:|---:|
| Continuous return, 2020-01-02–2026-09-10 | -0.11% | +5.07% |
| Annual return, 244 sessions/year | -0.02% | +0.75% |
| Maximum drawdown | 3.96% | 3.72% |
| Actual fills / completed round trips | 52 / 26 | 98 / 49 |
| Mean exposure | 2.34% | 3.66% |
| Independent later return, 2025-01-02–2026-09-10 | +2.37% | **-2.39%** |
| Candidate full-period cost stress | — | +4.09% |

The CSI 300 price index gained 11.03% over the full interval. Candidate annualized Sharpe was -1.04 with a 3% risk-free reference and no interest on cash. Candidate validation stress returned -0.70%, later stress -2.45%. Full-period performance improved but later performance deteriorated: gains mainly came from earlier conditions. Defaults remain unchanged; neither version establishes sustained profitability.

Baseline full history had already been inspected, so the later check is **not certified untouched out-of-sample data**. Independently restarted periods cannot simply be compounded to reconstruct the continuous path. Stress changes limit-fill eligibility and quantities, so trade paths may differ.

### Data treatment and reproduction

All candidates share 2019-01-02–2026-09-10 snapshots, identical stock membership, risk budgets and commissions. No stocks were replaced based on observed winners. China Shenhua has ten suspended sessions from 2025-08-04 through 2025-08-15 without fabricated fills; see its [resumption announcement](https://file.finance.qq.com/finance/hs/pdf/2025/08/16/1224500923.PDF).

Archived stocks are not native Tencent qfq. Native Shenhua qfq had nonpositive early observations, so **all eight stocks consistently use Tencent hfq scaled by a fixed terminal reference ratio**. The `_daily_qfq.csv` suffix is only for adapter compatibility. Volumes are shares. The formula is `input_OHLC[t] = hfq_OHLC[t] × qfq_close[2026-09-10] / hfq_close[2026-09-10]`. Terminal scaling affects price filters and round-lot sizing. Raw-price execution, corporate-action cash/share accounting, historical ST flags and point-in-time membership are missing. Results are approximations, not investable net returns. The benchmark is a price index, without a common explicit dividend-reinvestment ledger.

Repository file `research/sr_risk_budget_2026_09/results.json` records declarations, all configurations, failed gates, period/year metrics and input SHA-256. Market CSVs are not shipped with the code. Reproduction requires archived snapshots; new downloads or normalization conventions are different experiments.

```bash
python scripts/research_sr_risk_budget.py --candidate channel60 --period full \
  --data-dir /path/to/frozen-inputs --output reports/replay
python scripts/research_sr_risk_budget.py --candidate channel60 --period full --stress \
  --data-dir /path/to/frozen-inputs --output reports/replay
```

`--candidate` accepts the 11 table names; `--period` accepts `development`, `validation`, `later_check`, or `full`. Each invocation runs one configuration and period, without automatic selection or overwriting evidence. Auxiliary online index charts are omitted; benchmark metrics still use snapshots. Outputs contain fills, equity, events, parameters, costs and source hashes.

Further work should first obtain point-in-time membership and raw-price/corporate-action data, then declare new hypotheses and gates before new-data or paper-trading checks. Retuning inspected years creates no independent evidence. Multiple trials amplify selection bias; see [Bailey et al. on backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). No PBO estimate or statistical-significance claim was produced here.
