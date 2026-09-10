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

Files are named `<code>_daily_qfq.csv`, including `000300.XSHG_daily_qfq.csv`. The first column is a date index. Required columns are `open,high,low,close,volume`, with consistently forward-adjusted CNY prices and volume in shares. Cover the final test session and provide at least 160 valid warm-up bars before the start. Duplicate/unordered dates, nonfinite values, invalid OHLC, missing benchmark sessions or truncated coverage cause errors instead of silently shortening the evaluation. Missing stock sessions are recorded in the manifest, without inventing fills.

Offline runs use the packaged calendar and bind engine/report reads to the same immutable CSV frames, preventing a later download of different benchmark data. This example adapter is scoped to the Python process; do not run it concurrently in multiple threads.

Default commissions are 0.025% with a CNY 5 minimum, matching the shared examples. The engine applies date-aware sell stamp duty. Base one-way slippage is 0.1%; `--stress` reruns with twice the commission rates/minimum and 0.3% one-way slippage. See the [tax authority's announcement](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) for the stamp-duty reduction's effective date.

Outputs under `reports/sr_risk_budget/`:

| File | Purpose |
|---|---|
| `summary.json` | Fixed parameters, costs, input SHA-256 hashes, full-period/yearly metrics, cost stress results |
| `equity.csv` | Daily equity, cash, exposure and halt state |
| `trades.csv` | Actual engine fills and fees |
| `events.csv` | Buy limits, support, stops, targets, exit reasons, halt/resume events |

Calendar-year metrics slice one continuous position path and retain the prior equity observation at each boundary. They do not restart from cash each year and are not independent or certified untouched out-of-sample tests. There is no parameter search. Do not select only winning years to claim stable profits.

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
