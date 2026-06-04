# Glossary

This glossary explains professional terms commonly found in EasyQuant documentation and A-share quantitative backtesting.

---

## A

**Alpha**
The excess annualized return of a strategy relative to its benchmark (e.g., CSI 300), after adjusting for market risk — the "pure skill" component. A positive alpha means the strategy outperforms the benchmark at the same risk level.

**annualized return**
The total return over the holding period converted to an equivalent one-year rate. Formula: `(1 + total_return) ** (365 / days) - 1`.

---

## B

**backtest**
Simulating strategy execution on historical data to evaluate potential performance. EasyQuant uses an event-driven engine: each trading day sequentially calls `before_trading_start` → `run_daily` / `handle_data` → `after_trading_end`.

**benchmark**
The reference index used to measure strategy performance. Default is CSI 300 (`000300.XSHG`). Metrics such as Sharpe, alpha, and beta are all calculated relative to the benchmark.

**beta**
The sensitivity of strategy returns to benchmark returns. Beta = 1 means the strategy moves in lockstep with the benchmark; beta > 1 amplifies moves; beta < 1 dampens them.

**Brinson attribution**
Decomposes excess returns into allocation effect, selection effect, and interaction effect, quantifying the contribution of each decision layer.

**bootstrap**
A resampling statistical method: draws samples with replacement from the original data to generate a large number of simulated samples, used to estimate confidence intervals for metrics. EasyQuant provides this via `eqlib.scientific.bootstrap_metrics()`.

---

## C

**Calmar ratio**
Annualized return / absolute value of max drawdown. Measures how much annualized return is earned per unit of drawdown risk.

**context**
The object passed to every callback function during backtest / live trading by EasyQuant. Contains the current date (`context.current_dt`), portfolio state (`context.portfolio`), stock universe (`context.universe`), and other information.

---

## D

**drawdown**
The decline from a historical peak to the current level, usually expressed as a percentage. `max_drawdown` is the largest peak-to-trough decline over the entire backtest period and is the core measure of a strategy's downside risk.

---

## E

**event-driven**
EasyQuant's core architecture: instead of vectorized batch computation over all historical data, events are triggered sequentially in chronological order (daily open, close, data arrival), and the strategy responds via callback functions. This is consistent with the Zipline / JoinQuant design.

---

## G

**g (global object)**
An object used in EasyQuant strategies to store strategy-level global variables via `g.xxx = ...`, with a lifespan equal to the entire backtest run. Similar to JoinQuant's `g`.

---

## I

**Information Ratio (IR)**
Mean of excess returns (strategy − benchmark) / standard deviation of excess returns × √252. Measures how much excess return is earned per unit of active risk.

---

## L

**look-ahead bias**
Unintentionally using future data that was unknowable at the time during a backtest, causing inflated strategy performance. Common causes: calling real-time quote APIs directly, placing orders using the current day's close (should be next day's open), fundamental data not filtered by disclosure date.

**lot size**
The minimum buy unit in A-shares is 1 lot = 100 shares. EasyQuant's `order*` functions automatically round target share counts to multiples of 100 (under T+1 rules, same-day buy-sell of the same stock is not allowed).

---

## M

**mark-to-market**
Valuing positions at current market price rather than historical cost. `portfolio.total_value` is the total assets after real-time mark-to-market, including cash and position market values.

**max drawdown**
See drawdown.

**Monte Carlo simulation**
Simulates a large number of possible equity paths by randomly shuffling the return sequence, to evaluate the distribution of strategy metrics (e.g., Sharpe ratio, max drawdown). EasyQuant provides this via `eqlib.scientific.monte_carlo_simulation()`.

---

## N

**North-bound capital**
Capital flowing into A-shares from Hong Kong via Shanghai-Hong Kong Stock Connect and Shenzhen-Hong Kong Stock Connect, often regarded as a "smart money" indicator. Large net inflows are typically seen as bullish signals, while large net outflows are viewed as risk warnings. EasyQuant provides this data via `get_north_money_flow()`.

---

## O

**overfitting**
When strategy parameters are excessively tuned to specific noise in historical data, causing a significant drop in performance on new data. Common detection methods include out-of-sample testing, parameter sensitivity analysis, and walk-forward analysis. EasyQuant's `eqlib.scientific.overfitting` module provides automated detection tools.

---

## P

**pending order**
After placing an order with `order()` / `order_value()`, the order is not filled immediately but is placed in the `_pending_orders` queue, to be matched at the **next trading day's opening price** (T+1 rule).

**portfolio**
Accessed via `context.portfolio`, containing fields such as `available_cash`, `total_value`, and `positions` (a dictionary keyed by stock ticker).

---

## Q

**qfq / forward adjusted price**
Forward-adjusts historical stock prices for dividends, bonus shares, splits, and other corporate actions, making historical prices continuously comparable to current prices. EasyQuant uses forward-adjusted data by default (`adjust='qfq'`).

---

## R

**recorded_values**
Custom daily metrics written via `record(key=value)`, stored in `result['recorded_values']` keyed by date with dictionary values. Used to plot custom curves in reports.

**risk-free rate**
The benchmark return rate used when calculating Sharpe, Sortino, and other metrics. Defaults to the Chinese government bond annualized rate of 3% (`RISK_FREE_RATE = 0.03`).

**Restricted share unlock**
After the lock-up period expires, previously non-tradable shares gain listing eligibility. When a large unlock (> ¥5 billion) approaches, stock prices tend to come under pressure. EasyQuant provides this data via `get_restriction_release()`.

---

## S

**Sharpe ratio**
(Annualized return − annualized risk-free rate) / annualized volatility. Measures how much excess return is earned per unit of total risk. A Sharpe ratio > 1 is generally considered good.

**Sortino ratio**
(Annualized return − MAR) / downside standard deviation. Unlike Sharpe, it only considers downside volatility (returns below the Minimum Acceptable Return, MAR = 0), and does not penalize positive volatility.

**ST (Special Treatment)**
A special designation by the Shanghai and Shenzhen exchanges for stocks with abnormal business conditions (*ST / ST). ST stocks have a ±5% daily price limit. EasyQuant's `filter_st_stocks()` function can exclude ST stocks from the stock universe.

**Stamp duty**
A tax levied on sell-side transactions in A-shares. Currently 0.05% (halved since August 2023). Set via `close_tax=0.0005` in the `OrderCost` configuration.

**survivorship bias**
Using only currently listed stocks for backtesting while ignoring delisted or ST-designated stocks, causing inflated backtest returns. EasyQuant's `eqlib.scientific.check_survivorship_bias()` can detect this bias.

---

## T

**T+1**
A-share trading rule: shares bought today can only be sold starting the next trading day. EasyQuant enforces this via `_t1_locked_amounts` to prevent false same-day trading signals in backtests.

**trading calendar**
The A-share trading calendar, excluding holidays and weekends. EasyQuant prefers Sina Finance's `ak.tool_trade_date_hist_sina()` for precise trading dates, cached in `PreloadedData._dates`.

---

## U

**universe**
The set of stocks a strategy operates on, accessed via `context.universe`, set through `set_universe()` or by assignment in `initialize()`.

---

## V

**VaR (Value at Risk)**
The maximum expected loss a portfolio may suffer within a given holding period at a specified confidence level (e.g., 95%). EasyQuant provides calculation via `eqlib.scientific.value_at_risk()` and `utils.value_at_risk()`.

**CVaR (Conditional VaR)**
Also known as Expected Shortfall (ES). The expected loss given that losses exceed VaR, measuring tail risk. EasyQuant provides calculation via `eqlib.scientific.conditional_var()` and `utils.conditional_var()`.

---

## W

**walk-forward analysis**
Divides the historical period into alternating in-sample (IS) and out-of-sample (OOS) windows: parameters are optimized on the IS window and validated on the OOS window, then OOS curves are stitched together. Used to detect overfitting. EasyQuant provides this via `eqlib.wfa.walk_forward()`.

---

## Chinese Market Terms

**North-bound capital (北向资金)**
Capital flowing into A-shares from Hong Kong via Shanghai-Hong Kong Stock Connect and Shenzhen-Hong Kong Stock Connect, often regarded as a "smart money" indicator. Large net inflows are typically seen as bullish signals, while large net outflows are viewed as risk warnings. EasyQuant provides this data via `get_north_money_flow()`.

**Margin trading (融资融券)**
Leveraged trading where investors borrow funds from brokers to buy (margin buying) or borrow shares to sell short. A rapidly rising margin balance reflects overheated market sentiment, while a rapid decline reflects panic. EasyQuant provides this data via `get_margin_data()`.

**Limit up / Limit down (涨跌停)**
A-share daily price change limit system (main board ±10%, ChiNext / STAR Market ±20%). An abnormally high number of limit-down stocks is a systemic risk warning, while an abnormally high number of limit-up stocks may foreshadow a pullback. EasyQuant provides this data via `get_limit_up_down_stats()`.

**Restricted share unlock (限售股解禁)**
After the lock-up period expires, previously non-tradable shares gain listing eligibility. When a large unlock (> ¥5 billion) approaches, stock prices tend to come under pressure. EasyQuant provides this data via `get_restriction_release()`.

**Kill Switch**
A protection mechanism that automatically halts trading when risk metrics exceed thresholds. EasyQuant's `PortfolioRiskMonitor` supports single-strategy drawdown kill switches, portfolio-level drawdown kill switches, correlation kill switches, and market stress kill switches.
