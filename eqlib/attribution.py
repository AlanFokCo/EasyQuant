"""Attribution analysis for backtest results.

Provides:
- Risk/return metrics (Sharpe, Sortino, max drawdown, Calmar, alpha, beta)
- Trade-level win rate (matched round-trip buy/sell pairs, net of fees)
- Turnover and total commission cost metrics
- Single-period Brinson-Hood-Beebower attribution (allocation, selection,
  interaction effects) over the backtest window; mathematically closed:
  the three effects always sum to the total active return
- Fama-French factor analysis

Benchmark-dependent metrics (alpha, beta, information_ratio, excess_return,
benchmark_return, benchmark_volatility) are ``float("nan")`` when benchmark
data is unavailable, so an offline/failed benchmark fetch can never be
mistaken for a real computed value.
"""

import datetime
import numpy as np
import pandas as pd
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR


def analyze_returns(result, risk_free_rate=RISK_FREE_RATE, trading_days=TRADING_DAYS_PER_YEAR):
    """Calculate comprehensive risk and return metrics from a backtest result.

    Parameters:
        result: dict returned by run_backtest or run_strategy
        risk_free_rate: annual risk-free rate (default 0.03)
        trading_days: number of trading days per year (default 244)

    Returns:
        dict with metrics including:
            total_return, annual_return, annual_volatility, sharpe_ratio,
            sortino_ratio, max_drawdown, calmar_ratio, alpha, beta,
            information_ratio,
            win_rate_daily: daily win rate (fraction of profitable days),
            win_rate_trade: round-trip trade win rate (FIFO-matched buy/sell
                pairs, net of commissions, taxes and slippage — a round trip
                only counts as a win when its cash-flow P&L is positive),
            trade_count: number of completed round-trip trades,
            win_count, loss_count: separate win/loss trade counts,
            profit_loss_ratio: avg winning trade P&L / avg losing trade P&L,
            annual_turnover: total traded value / avg portfolio value / years,
            total_commission: sum of all commissions paid,
            net_return: same as total_return; cash path in the engine already
                pays commissions, so portfolio value is net of fees. The
                ``total_commission`` field sums fees for reporting only.
            excess_return: strategy total return minus benchmark total return,
            benchmark_return: benchmark total return over the same period,
            excess_return_max_drawdown: max drawdown of daily excess returns,
            excess_return_sharpe: Sharpe ratio of daily excess returns,
            daily_excess_return: annualized mean daily excess return,
            benchmark_volatility: annualized benchmark volatility.

    Benchmark-dependent fields (alpha, beta, information_ratio, excess_return,
    benchmark_return, excess_return_max_drawdown, excess_return_sharpe,
    daily_excess_return, benchmark_volatility) are NaN when benchmark data
    cannot be obtained.  Benchmark prices are taken from
    ``result["benchmark_values"]`` (recorded by the engine) when present;
    otherwise a fresh ``fetch_stock_data`` call is attempted.
    """
    ctx = result["context"]
    trades = result["trade_log"]
    recorded = result["recorded_values"]

    if not recorded:
        return None

    # Build daily portfolio value series
    if isinstance(recorded, dict):
        entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min))
    else:
        entries = recorded

    if not entries or "total_value" not in entries[0]:
        return None

    values = pd.Series(
        [r["total_value"] for r in entries],
        index=pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in entries]),
    )

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    if initial <= 0:
        return None
    total_return = (final - initial) / initial

    # Daily returns
    daily_ret = values.pct_change().dropna()
    if daily_ret.empty:
        return None

    n_days = len(daily_ret)
    ann_factor = trading_days

    # Annualized return (geometric)
    cum_ret = (1 + daily_ret).prod()
    ann_return = cum_ret ** (ann_factor / n_days) - 1

    # Annualized volatility
    std = daily_ret.std()
    ann_vol = std * np.sqrt(ann_factor)

    # Sharpe ratio
    daily_rf = risk_free_rate / ann_factor
    # Handle NaN from std calculation (empty or single-element series)
    if pd.isna(std) or std <= 0:
        sharpe = 0.0
    else:
        sharpe = (daily_ret.mean() - daily_rf) / std * np.sqrt(ann_factor)
        if not np.isfinite(sharpe):
            sharpe = 0.0

    # Sortino ratio — downside deviation (LPM2 around risk-free rate)
    # Correct formula: sqrt(mean(min(R_t - rf, 0)^2)), not std(negative returns).
    downside_diff = (daily_ret - daily_rf).clip(upper=0)
    downside_dev = float((downside_diff ** 2).mean() ** 0.5) * np.sqrt(ann_factor)
    if downside_dev <= 0 or not np.isfinite(downside_dev):
        sortino = 0.0
    else:
        sortino = ((daily_ret.mean() * ann_factor - risk_free_rate) / downside_dev)
        if not np.isfinite(sortino):
            sortino = 0.0

    # Max drawdown
    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max
    max_dd = drawdown.min()
    # Handle NaN drawdown
    if pd.isna(max_dd):
        max_dd = 0.0
        dd_end_idx = values.index[-1] if not values.empty else None
        dd_start_idx = values.index[0] if not values.empty else None
    else:
        dd_end_idx = drawdown.idxmin()
        # Handle case where idxmin might return None or invalid index
        if pd.isna(dd_end_idx) or dd_end_idx not in values.index:
            dd_end_idx = values.index[-1] if not values.empty else None
            dd_start_idx = values.index[0] if not values.empty else None
        else:
            peak_slice = values[:dd_end_idx]
            dd_start_idx = peak_slice.idxmax() if not peak_slice.empty else values.index[0]

    # Calmar ratio — use a small threshold to avoid explosive values when
    # max drawdown is near-zero (e.g. -1e-10 would produce a ratio of 1e10).
    calmar = ann_return / abs(max_dd) if abs(max_dd) >= 1e-6 else 0.0

    # Win rate (by day)
    win_rate_daily = float((daily_ret > 0).sum()) / n_days

    # ── Trade-level win rate (item 12) ────────────────────────────────────
    win_rate_trade, trade_count, win_count, loss_count = _calc_trade_win_rate(trades)

    # ── Profit/Loss ratio ─────────────────────────────────────────────────
    profit_loss_ratio, _, _ = _calc_profit_loss_ratio(trades)

    # ── Turnover & commission metrics (item 13) ───────────────────────────
    years = n_days / ann_factor if ann_factor > 0 else 1.0
    avg_portfolio_value = float(values.mean()) if not values.empty else initial
    total_buy_value = sum(
        t["price"] * t["amount"]
        for t in trades if t.get("type") == "BUY"
    )
    total_sell_value = sum(
        t["price"] * t["amount"]
        for t in trades if t.get("type") == "SELL"
    )
    annual_turnover = ((total_buy_value + total_sell_value) / 2.0 / avg_portfolio_value / years
                       if avg_portfolio_value > 0 and years > 0 else 0.0)
    total_commission = sum(t.get("commission", 0.0) for t in trades)
    # total_return is from mark-to-market portfolio value; buys/sells already
    # reduced cash by commissions in the engine — do not subtract fees again.
    net_return = total_return

    # Benchmark comparison.  Prefer the engine-recorded benchmark price series
    # (result["benchmark_values"]) so that alpha/beta/IR share the exact same
    # benchmark data the backtest ran with and no extra network fetch is made;
    # fall back to a fresh fetch only when the engine recorded nothing.
    benchmark_name = result.get("benchmark", "000300.XSHG")
    bench_prices = _benchmark_prices_from_result(result)
    alpha, beta, info_ratio, bench_daily_ret, bench_total_ret, bench_ann_vol = _calc_alpha_beta(
        daily_ret, benchmark_name, risk_free_rate, ann_factor,
        benchmark_prices=bench_prices,
    )

    # Excess return metrics — NaN when the benchmark series is unavailable so
    # that "no data" can never be mistaken for a real computed number.
    if bench_daily_ret is not None:
        excess_total, excess_max_dd, excess_sharpe, daily_excess_ret = _calc_excess_metrics(
            daily_ret, bench_daily_ret, risk_free_rate, ann_factor
        )
    else:
        excess_total = float("nan")
        excess_max_dd = float("nan")
        excess_sharpe = float("nan")
        daily_excess_ret = float("nan")

    # ── Monthly returns ─────────────────────────────────────────────
    monthly_returns = {}
    monthly_vals = values.resample("ME").last()
    prev_val = initial
    for dt, val in monthly_vals.items():
        if pd.notna(val) and prev_val > 0:
            monthly_returns[dt.strftime("%Y-%m")] = round(float(val / prev_val - 1), 6)
            prev_val = val

    # ── Rolling metrics (60 trading-day window) ─────────────────────
    window = min(60, n_days)
    rolling_mean = daily_ret.rolling(window).mean()
    rolling_std = daily_ret.rolling(window).std()
    rolling_sharpe_60d = []
    rolling_volatility_60d = []
    if window >= 10 and not rolling_std.dropna().empty:
        for dt in rolling_mean.dropna().index:
            rm = rolling_mean.loc[dt]
            rs = rolling_std.loc[dt]
            if rs > 0 and np.isfinite(rm) and np.isfinite(rs):
                s = float((rm - daily_rf) / rs * np.sqrt(ann_factor))
                v = float(rs * np.sqrt(ann_factor))
                rolling_sharpe_60d.append({"date": dt.strftime("%Y-%m-%d"), "value": round(s, 3)})
                rolling_volatility_60d.append({"date": dt.strftime("%Y-%m-%d"), "value": round(v, 4)})

    # ── Daily returns statistics ─────────────────────────────────────
    from scipy.stats import skew, kurtosis
    dr_array = daily_ret.values
    daily_returns_stats = {
        "mean": float(daily_ret.mean()),
        "std": float(daily_ret.std()),
        "skewness": float(skew(dr_array)) if len(dr_array) > 3 else 0.0,
        "kurtosis": float(kurtosis(dr_array)) if len(dr_array) > 3 else 0.0,
        "best_day": float(daily_ret.max()),
        "worst_day": float(daily_ret.min()),
        "positive_days": int((daily_ret > 0).sum()),
        "negative_days": int((daily_ret < 0).sum()),
        "histogram": [
            {"bin": round(b, 4), "count": int(((daily_ret >= b) & (daily_ret < b + 0.005)).sum())}
            for b in np.arange(-0.05, 0.05, 0.005)
        ],
    }

    # ── Per-stock P&L (net of fees, same FIFO caliber as the engine cash) ──
    per_stock_pnl = {}
    for rt in _match_round_trips(trades):
        sec = rt["security"]
        per_stock_pnl[sec] = per_stock_pnl.get(sec, 0.0) + rt["pnl"]

    # ── Top 5 drawdown periods ──────────────────────────────────────
    _peak = values.cummax()
    _dd = (values - _peak) / _peak
    drawdown_periods = []
    in_dd = False
    dd_start = dd_trough = None
    dd_depth = 0.0
    for dt, dd_val in _dd.items():
        if dd_val < 0:
            if not in_dd:
                in_dd = True
                dd_start = dt
                dd_trough = dt
                dd_depth = dd_val
            elif dd_val < dd_depth:
                dd_trough = dt
                dd_depth = dd_val
        else:
            if in_dd and dd_start is not None:
                drawdown_periods.append({
                    "start": dd_start.strftime("%Y-%m-%d"),
                    "trough": dd_trough.strftime("%Y-%m-%d"),
                    "recovery": dt.strftime("%Y-%m-%d"),
                    "depth": round(float(dd_depth), 4),
                    "duration_days": (dt - dd_start).days,
                    "recovery_days": (dt - dd_trough).days,
                })
                in_dd = False
    if in_dd and dd_start is not None:
        last_dt = values.index[-1]
        drawdown_periods.append({
            "start": dd_start.strftime("%Y-%m-%d"),
            "trough": dd_trough.strftime("%Y-%m-%d"),
            "recovery": None,
            "depth": round(float(dd_depth), 4),
            "duration_days": (last_dt - dd_start).days,
            "recovery_days": None,
        })
    drawdown_periods.sort(key=lambda x: x["depth"])
    for i, dp in enumerate(drawdown_periods[:5]):
        dp["rank"] = i + 1
    drawdown_periods = drawdown_periods[:5]

    return {
        "total_return": total_return,
        "annual_return": ann_return,
        "annual_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "max_drawdown_start": dd_start_idx.date() if pd.notna(dd_start_idx) else None,
        "max_drawdown_end": dd_end_idx.date() if pd.notna(dd_end_idx) else None,
        "calmar_ratio": calmar,
        "alpha": alpha,
        "beta": beta,
        "information_ratio": info_ratio,
        "win_rate": win_rate_daily,           # backward-compatible alias
        "win_rate_daily": win_rate_daily,
        "win_rate_trade": win_rate_trade,
        "trade_count": trade_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "profit_loss_ratio": profit_loss_ratio,
        "annual_turnover": annual_turnover,
        "total_commission": total_commission,
        "net_return": net_return,
        "trading_days": n_days,
        "num_trades": len(trades),
        # Excess return metrics
        "excess_return": excess_total,
        "benchmark_return": bench_total_ret,
        "excess_return_max_drawdown": excess_max_dd,
        "excess_return_sharpe": excess_sharpe,
        "daily_excess_return": daily_excess_ret,
        "benchmark_volatility": bench_ann_vol,
        # New fields for enhanced reports
        "monthly_returns": monthly_returns,
        "rolling_sharpe_60d": rolling_sharpe_60d,
        "rolling_volatility_60d": rolling_volatility_60d,
        "daily_returns_stats": daily_returns_stats,
        "per_stock_pnl": per_stock_pnl,
        "drawdown_periods": drawdown_periods,
    }


def _match_round_trips(trades):
    """FIFO-match SELL fills against BUY lots, net of all transaction costs.

    Each matched round trip uses the same cash-flow caliber as the engine:
    the buy side costs ``price * amount + commission`` and the sell side
    yields ``price * amount - commission`` (the engine's ``commission`` field
    already bundles commissions, stamp duty and any transfer fees; slippage
    is embedded in the executed price).  Fees of partially matched fills are
    amortized pro-rata over the matched shares.

    Returns:
        list of dicts with keys: security, amount (matched shares), pnl
        (net profit in yuan), buy_cost, sell_proceeds.
    """
    from collections import deque

    buy_queues: dict = {}    # security -> deque of (price, amount, commission)
    round_trips = []

    for trade in trades:
        sec = trade["security"]
        t_type = trade.get("type")
        if t_type not in ("BUY", "SELL"):
            continue
        price = trade["price"]
        amount = trade["amount"]
        commission = trade.get("commission", 0.0) or 0.0

        if t_type == "BUY":
            buy_queues.setdefault(sec, deque()).append((price, amount, commission))

        elif t_type == "SELL":
            remaining = amount
            q = buy_queues.get(sec, deque())
            matched_cost = 0.0
            total_matched = 0

            while remaining > 0 and q:
                buy_price, buy_amt, buy_comm = q[0]
                matched = min(buy_amt, remaining)
                matched_cost += buy_price * matched
                if buy_amt > 0 and buy_comm:
                    matched_cost += buy_comm * (matched / buy_amt)
                total_matched += matched
                remaining -= matched
                if matched == buy_amt:
                    q.popleft()
                else:
                    q[0] = (buy_price, buy_amt - matched,
                            buy_comm * (1 - matched / buy_amt) if buy_amt > 0 else 0.0)

            if total_matched > 0:
                sell_comm = commission * (total_matched / amount) if amount > 0 else 0.0
                proceeds = price * total_matched - sell_comm
                round_trips.append({
                    "security": sec,
                    "amount": total_matched,
                    "pnl": proceeds - matched_cost,
                    "buy_cost": matched_cost,
                    "sell_proceeds": proceeds,
                })

    return round_trips


def _calc_trade_win_rate(trades):
    """Compute win rate by completed round-trip buy/sell pairs (item 12).

    Uses FIFO matching: each sell is matched against the oldest outstanding
    buy lot for that security.  A completed round trip is a "win" only when
    its net P&L — after both buy-side and sell-side commissions/taxes — is
    positive, matching the engine's cash accounting exactly.

    Returns:
        tuple: (win_rate, completed_trade_count, win_count, loss_count)
    """
    round_trips = _match_round_trips(trades)
    wins = sum(1 for rt in round_trips if rt["pnl"] > 0)
    total = len(round_trips)
    losses = total - wins
    win_rate = wins / total if total > 0 else 0.0
    return win_rate, total, wins, losses


def _calc_profit_loss_ratio(trades):
    """Compute avg win / avg loss from FIFO-matched trade pairs.

    For each completed round-trip, compute the total P&L in yuan net of all
    transaction costs (sell_proceeds - buy_cost, fees included).  Then
    separate wins and losses, compute their averages, and return the ratio.

    Returns:
        tuple: (profit_loss_ratio, win_count, loss_count)
               profit_loss_ratio = avg_win / abs(avg_loss), or 0.0 if no losses.
    """
    round_trips = _match_round_trips(trades)
    win_pnls = [rt["pnl"] for rt in round_trips if rt["pnl"] > 0]
    loss_pnls = [rt["pnl"] for rt in round_trips if rt["pnl"] <= 0]

    win_count = len(win_pnls)
    loss_count = len(loss_pnls)

    if win_count == 0:
        return 0.0, win_count, loss_count
    if loss_count == 0:
        return float("inf"), win_count, loss_count

    avg_win = sum(win_pnls) / win_count
    avg_loss = sum(loss_pnls) / loss_count
    plr = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    return plr, win_count, loss_count


def _calc_excess_metrics(strategy_daily_ret, benchmark_daily_ret, risk_free_rate, ann_factor):
    """Compute excess return metrics.

    Returns:
        tuple: (excess_return, excess_return_max_drawdown, excess_return_sharpe, daily_excess_return)
    """
    # Guard against NaN entries in benchmark (e.g. missing trading days)
    benchmark_daily_ret = benchmark_daily_ret.fillna(0.0)
    excess = strategy_daily_ret - benchmark_daily_ret
    excess_total = float((1 + excess).prod() - 1)
    excess_daily_mean = float(excess.mean()) * ann_factor

    # Excess Sharpe (= Information Ratio): excess return is already
    # strategy - benchmark; subtracting rf again would be double-counting.
    exc_std = excess.std()
    excess_sharpe = excess.mean() / exc_std * np.sqrt(ann_factor) if exc_std > 0 else 0.0

    # Excess return max drawdown
    excess_cum = (1 + excess).cumprod()
    excess_rolling_max = excess_cum.cummax()
    excess_dd = ((excess_cum - excess_rolling_max) / excess_rolling_max).min()

    return excess_total, float(excess_dd), excess_sharpe, excess_daily_mean


def _benchmark_prices_from_result(result):
    """Build a benchmark close-price Series from ``result["benchmark_values"]``.

    The engine records benchmark_values as ``[{"date": ..., "value": close}]``
    at the end of each backtest.  Returns a sorted, de-duplicated pd.Series of
    float closes indexed by Timestamp, or None when unavailable/insufficient.
    """
    raw_values = result.get("benchmark_values")
    if not isinstance(raw_values, list) or not raw_values:
        return None
    rows = []
    for item in raw_values:
        if not isinstance(item, dict):
            continue
        try:
            date = pd.Timestamp(item.get("date"))
            value = float(item.get("value"))
        except (TypeError, ValueError, OverflowError):
            continue
        if pd.isna(date) or not np.isfinite(value) or value <= 0:
            continue
        rows.append((date, value))
    if len(rows) < 2:
        return None
    series = pd.Series(
        [value for _date, value in rows],
        index=pd.DatetimeIndex([date for date, _value in rows]),
    )
    return series[~series.index.duplicated(keep="last")].sort_index()


def _calc_alpha_beta(strategy_returns, benchmark_code, rf_rate, ann_factor,
                     benchmark_prices=None):
    """Calculate alpha, beta, information ratio vs benchmark, plus benchmark series.

    Args:
        strategy_returns: pd.Series of strategy daily returns.
        benchmark_code: e.g. "000300.XSHG" — only used for the fallback fetch.
        rf_rate: annual risk-free rate.
        ann_factor: trading days per year.
        benchmark_prices: optional pd.Series of benchmark close prices indexed
            by date (typically from ``result["benchmark_values"]``).  When
            given, no network fetch is attempted.

    Alpha/beta/information ratio require at least 10 overlapping trading days.
    When benchmark data is unavailable or the overlap is insufficient, the
    affected statistics are returned as NaN (never as plausible-looking
    defaults such as alpha=0.0/beta=1.0) so callers can render them as "N/A".

    Returns:
        tuple: (alpha_annual, beta, info_ratio, benchmark_daily_ret,
                benchmark_total_return, benchmark_annual_volatility)
        Unavailable scalar fields are NaN; an unavailable daily series is None.
    """
    nan = float("nan")
    default = (nan, nan, nan, None, nan, nan)
    try:
        if benchmark_prices is not None and len(benchmark_prices) >= 2:
            bench_close = benchmark_prices
        else:
            from eqlib.data import fetch_stock_data

            start = strategy_returns.index[0] - datetime.timedelta(days=30)
            end = strategy_returns.index[-1]

            bench_df = fetch_stock_data(benchmark_code, start, end)
            if bench_df.empty or "close" not in bench_df.columns:
                return default
            bench_close = bench_df["close"]

        bench_ret = bench_close.pct_change().dropna()

        # Use the intersection of dates — fillna(0) would treat missing days
        # as "benchmark returned 0%" which biases beta low and alpha high.
        common = strategy_returns.index.intersection(bench_ret.index)
        if len(common) < 2:
            return default

        # Benchmark series statistics are meaningful with any >= 2 points.
        bench_daily_ret = pd.Series(bench_ret.loc[common].values, index=common)
        bench_total_ret = float((1 + bench_daily_ret).prod() - 1)
        bench_std = bench_daily_ret.std()
        bench_ann_vol = (float(bench_std * np.sqrt(ann_factor))
                         if pd.notna(bench_std) else nan)

        if len(common) < 10:
            return nan, nan, nan, bench_daily_ret, bench_total_ret, bench_ann_vol

        strat = strategy_returns.loc[common].values
        bench = bench_daily_ret.values

        cov_matrix = np.cov(strat, bench, ddof=1)
        # Handle NaN in covariance matrix (can occur with NaN inputs)
        if not np.isfinite(cov_matrix).all():
            return nan, nan, nan, bench_daily_ret, bench_total_ret, bench_ann_vol
        bench_var = cov_matrix[1, 1]
        if bench_var < 1e-15:
            return nan, nan, nan, bench_daily_ret, bench_total_ret, bench_ann_vol

        beta = cov_matrix[0, 1] / bench_var
        # D1: Include risk-free rate in CAPM alpha computation
        daily_rf = rf_rate / ann_factor
        alpha_daily = (strat.mean() - daily_rf) - beta * (bench.mean() - daily_rf)
        alpha_annual = alpha_daily * ann_factor

        active = strat - bench
        active_mean = active.mean()
        active_std = active.std(ddof=1)
        info_ratio = (active_mean / active_std * np.sqrt(ann_factor)
                      if active_std > 0 else 0.0)

        return alpha_annual, beta, info_ratio, bench_daily_ret, bench_total_ret, bench_ann_vol
    except Exception:
        return default


def brinson_attribution(result, sector_data=None, benchmark_returns=None):
    """Single-period Brinson-Hood-Beebower attribution over the backtest window.

    Decomposes the total active return (portfolio return minus benchmark
    return) into the three classic BHB effects at the sector level:

        allocation  = Σ_i (w_p_i − w_b_i) · r_b_i
        selection   = Σ_i w_b_i · (r_p_i − r_b_i)
        interaction = Σ_i (w_p_i − w_b_i) · (r_p_i − r_b_i)

    The decomposition is mathematically closed by construction:
    allocation + selection + interaction == portfolio_return − benchmark_return.

    Parameters:
        result: dict returned by run_backtest
        sector_data: dict mapping security -> sector name.  Genuinely drives
            the grouping; securities missing from the mapping fall into
            "Unclassified".  When None, every security sits in a single
            sector, so allocation and interaction are identically zero and
            the whole active return is reported as selection — that is the
            correct BHB statement when no sector structure is known.
        benchmark_returns: optional pd.Series of benchmark daily returns
            indexed by date.  When given, the benchmark is this scalar total
            return applied uniformly across sectors (benchmark sector weights
            still come from the universe composition); without per-sector
            benchmark returns the allocation effect is zero by construction.
            When None, the benchmark is the equal-weight buy-and-hold return
            of the backtest universe per sector.

    Portfolio-side notes: per-security holding-period returns come from the
    trade log (realized cash flows, net of fees) plus the terminal market
    value of open positions; sector weights use cumulative buy-cost shares —
    a documented approximation, since the result dict carries no daily
    position weights.

    Benchmark-side notes: per-constituent buy-and-hold returns prefer the
    engine-exported OHLCV panel (result["ohlcv_data"], first→last close of
    the same qfq series the engine traded on); constituents without data
    contribute a 0.0 return.

    Returns:
        dict with allocation_effect, selection_effect, interaction_effect,
        total_active_return, portfolio_return, benchmark_return,
        benchmark_model ("universe_equal_weight" or "scalar_series") and a
        per-sector breakdown under "sectors"; or None if no trades or
        positions exist.
    """
    ctx = result["context"]
    trade_log = result.get("trade_log", [])
    positions = ctx.portfolio.positions

    if not trade_log and not positions:
        return None

    total_value = ctx.portfolio.total_value
    if total_value <= 0:
        return None

    # ── Portfolio side: per-security holding-period returns ──────────────
    buy_cost_by_sec: dict = {}
    sell_proceeds_by_sec: dict = {}
    for trade in trade_log:
        sec = trade["security"]
        if trade["type"] == "BUY":
            buy_cost_by_sec[sec] = buy_cost_by_sec.get(sec, 0.0) + (
                trade["price"] * trade["amount"] + trade.get("commission", 0.0)
            )
        elif trade["type"] == "SELL":
            sell_proceeds_by_sec[sec] = sell_proceeds_by_sec.get(sec, 0.0) + (
                trade["price"] * trade["amount"] - trade.get("commission", 0.0)
            )

    all_secs = set(buy_cost_by_sec) | set(positions)
    sec_returns: dict = {}
    for sec in all_secs:
        buy_cost = buy_cost_by_sec.get(sec, 0.0)
        if buy_cost <= 0:
            sec_returns[sec] = 0.0
            continue
        sell_proceeds = sell_proceeds_by_sec.get(sec, 0.0)
        pos = positions.get(sec)
        remaining = pos.total_value if pos else 0.0
        sec_returns[sec] = (sell_proceeds + remaining) / buy_cost - 1.0

    # Portfolio weights by total buy cost (proxy for average allocation over
    # the backtest period, including positions that were fully closed before
    # end-of-period — these would be missing from terminal positions alone).
    total_buy_cost = sum(buy_cost_by_sec.values())
    if total_buy_cost > 0:
        weights = {sec: cost / total_buy_cost for sec, cost in buy_cost_by_sec.items()}
    else:
        # Fall back to terminal open-position market value
        weights = {
            sec: pos.total_value / total_value
            for sec, pos in positions.items()
        }

    # ── Sectors ───────────────────────────────────────────────────────────
    universe = list(ctx.universe or sorted(all_secs))
    sector_of = {}
    for sec in set(universe) | all_secs:
        sector = sector_data.get(sec) if sector_data else None
        sector_of[sec] = str(sector) if sector else "Unclassified"
    sectors = sorted(set(sector_of.values()))

    # ── Benchmark side ────────────────────────────────────────────────────
    ohlcv_data = result.get("ohlcv_data") or {}
    if benchmark_returns is not None and isinstance(benchmark_returns, pd.Series):
        bench_model = "scalar_series"
        bench_total = float((1 + benchmark_returns).prod() - 1)
        # Scalar benchmark: every sector shares the same benchmark return.
        bench_sec_return = {sec: bench_total for sec in universe}
    else:
        bench_model = "universe_equal_weight"
        bench_sec_return = {}
        for sec in universe:
            df = ohlcv_data.get(sec)
            ret = None
            if df is not None and hasattr(df, "empty") and not df.empty and "close" in df.columns:
                closes = df["close"].dropna()
                closes = closes[closes > 0]
                if len(closes) >= 2:
                    ret = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
            if ret is None:
                # Constituent without price data: fall back to its traded
                # return when available, else 0.0 (documented limitation).
                ret = sec_returns.get(sec, 0.0)
            bench_sec_return[sec] = ret
        bench_total = (
            sum(bench_sec_return.values()) / len(bench_sec_return)
            if bench_sec_return else 0.0
        )

    # Sector benchmark weights: equal-weight universe composition.
    n_universe = len(universe)
    w_b = {s: 0.0 for s in sectors}
    if n_universe > 0:
        for sec in universe:
            w_b[sector_of[sec]] += 1.0 / n_universe

    # Sector portfolio weights and returns (cost-weighted aggregates).
    w_p = {s: 0.0 for s in sectors}
    for sec, w in weights.items():
        w_p[sector_of[sec]] = w_p.get(sector_of[sec], 0.0) + w

    r_b = {}
    for s in sectors:
        members = [sec for sec in universe if sector_of[sec] == s]
        r_b[s] = (sum(bench_sec_return.get(sec, 0.0) for sec in members) / len(members)
                  if members else 0.0)

    r_p = {}
    for s in sectors:
        members = [sec for sec in weights if sector_of.get(sec) == s]
        w_sum = sum(weights[sec] for sec in members)
        r_p[s] = (sum(weights[sec] * sec_returns.get(sec, 0.0) for sec in members) / w_sum
                  if w_sum > 0 else 0.0)

    # ── BHB effects (closed by construction) ──────────────────────────────
    sector_rows = {}
    allocation = 0.0
    selection = 0.0
    interaction = 0.0
    for s in sectors:
        a = (w_p.get(s, 0.0) - w_b.get(s, 0.0)) * r_b[s]
        sel = w_b.get(s, 0.0) * (r_p.get(s, 0.0) - r_b[s])
        inter = (w_p.get(s, 0.0) - w_b.get(s, 0.0)) * (r_p.get(s, 0.0) - r_b[s])
        allocation += a
        selection += sel
        interaction += inter
        sector_rows[s] = {
            "weight_portfolio": w_p.get(s, 0.0),
            "weight_benchmark": w_b.get(s, 0.0),
            "return_portfolio": r_p.get(s, 0.0),
            "return_benchmark": r_b[s],
            "allocation": a,
            "selection": sel,
            "interaction": inter,
        }

    portfolio_return = sum(w_p[s] * r_p.get(s, 0.0) for s in sectors)
    benchmark_return = sum(w_b[s] * r_b[s] for s in sectors)
    total_active = portfolio_return - benchmark_return

    return {
        "allocation_effect": allocation,
        "selection_effect": selection,
        "interaction_effect": interaction,
        "total_active_return": total_active,
        "portfolio_return": portfolio_return,
        "benchmark_return": benchmark_return,
        "benchmark_model": bench_model,
        "sectors": sector_rows,
    }


def simple_factor_analysis(result, factors=None):
    """Market beta and momentum regression.

    NOTE: This is NOT a Fama-French factor model. It performs a simple
    two-factor regression (market excess return + momentum proxy).
    For true multi-factor analysis, use SMB/HML factor data.

    Decomposes strategy returns into:
    - Market factor (beta vs benchmark)
    - Momentum proxy (lag-5 return autocorrelation, not a true UMD factor)
    - Alpha (residual vs market)

    .. note::
        Previously exported as ``fama_french_analysis`` (deprecated alias
        retained for backward compatibility).

    Parameters:
        result: dict from run_backtest
        factors: optional pre-computed factor returns DataFrame

    Returns:
        dict with factor exposures and alpha
    """
    recorded = result["recorded_values"]

    if not recorded:
        return None

    if isinstance(recorded, dict):
        entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min))
    else:
        entries = recorded

    if "total_value" not in entries[0]:
        return None

    values = pd.Series(
        [r["total_value"] for r in entries],
        index=pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in entries]),
    )
    strat_ret = values.pct_change().dropna()

    if strat_ret.empty or len(strat_ret) < 30:
        return None

    benchmark = result.get("benchmark", "000300.XSHG")
    alpha_annual, beta, _, _, _, _ = _calc_alpha_beta(strat_ret, benchmark, 0.03, TRADING_DAYS_PER_YEAR)

    arr = strat_ret.values
    if len(arr) > 10:
        with np.errstate(invalid="ignore"):
            momentum_corr = float(np.corrcoef(arr[:-5], arr[5:])[0, 1])
        if not np.isfinite(momentum_corr):
            momentum_corr = 0.0
    else:
        momentum_corr = 0.0

    rolling_vol = strat_ret.rolling(20).std()
    vol_of_vol = float(rolling_vol.std()) if not rolling_vol.dropna().empty else 0.0

    residual_vol = 0.0
    explained_var = 0.0
    try:
        from eqlib.data import fetch_stock_data

        start = strat_ret.index[0] - datetime.timedelta(days=30)
        end = strat_ret.index[-1]
        bench_df = fetch_stock_data(benchmark, start, end)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_ret = bench_df["close"].pct_change().dropna()
            # Use intersection — fillna(0) would bias beta/covariance here,
            # which would then propagate to the residual and explained_variance.
            common = strat_ret.index.intersection(bench_ret.index)
            s = strat_ret.loc[common].values
            b = bench_ret.loc[common].values
            if len(s) > 1:
                residual = s - beta * b
                residual_vol = float(residual.std(ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR)
                strat_var = s.var(ddof=1)
                explained_var = float(
                    np.clip(1.0 - residual.var(ddof=1) / strat_var, 0.0, 1.0)
                ) if strat_var > 0 else 0.0
    except Exception:
        pass

    return {
        "market_beta": beta,
        "market_exposure": beta - 1.0,
        "alpha_annual": alpha_annual,
        "momentum_correlation": momentum_corr,
        "vol_of_vol": vol_of_vol,
        "residual_volatility": residual_vol,
        "explained_variance": explained_var,
    }


def fama_french_analysis(result, factors=None):
    """Deprecated alias for :func:`simple_factor_analysis`.

    .. deprecated::
        Use ``simple_factor_analysis`` instead.  This alias will be removed
        in a future release.  ``fama_french_analysis`` was a misleading name
        because the function does not implement the true Fama-French 3-factor
        model (no SMB/HML factor data).

    Example migration::

        # Before
        result = fama_french_analysis(backtest_result)

        # After
        result = simple_factor_analysis(backtest_result)
    """
    import warnings
    warnings.warn(
        "fama_french_analysis() is deprecated and will be removed in a future release. "
        "Use simple_factor_analysis() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return simple_factor_analysis(result, factors=factors)


def _finite_or(value, default=0.0):
    """Return float(value) when it is finite, else default (None/NaN/inf-safe)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if np.isfinite(v) else default


def grade_strategy(analytics) -> dict:
    """Compute 6-dimension scores, overall grade, and summary text.

    See spec: docs/superpowers/specs/2026-06-05-report-enhancement-design.md §4

    Returns:
        dict with keys: overall (str), score (float), dimensions (list of dicts),
        weakest (str), strongest (str), summary_text (str).
    """
    if analytics is None:
        return {"overall": "D", "score": 0, "dimensions": [],
                "weakest": "", "strongest": "", "summary_text": "Insufficient data."}

    dims = []

    # --- Return Capability (weight 0.20) ---
    ann_ret = _finite_or(analytics.get("annual_return", 0))
    # Benchmark-dependent metrics may be NaN (benchmark unavailable); they
    # contribute zero bonus rather than crashing or faking a real value.
    alpha = _finite_or(analytics.get("alpha", 0))
    ret_score = max(0, min(100, ann_ret / 0.25 * 100))
    alpha_bonus = max(0, min(15, alpha / 0.01 * 5))
    ret_score = min(100, ret_score + alpha_bonus)
    dims.append({"name": "return_capability", "score": round(ret_score, 1),
                 "key": {"annual_return": ann_ret, "alpha": alpha}})

    # --- Risk Control (weight 0.20) ---
    max_dd = abs(analytics.get("max_drawdown", 0))
    vol = analytics.get("annual_volatility", 0)
    dd_score = 100 if max_dd < 0.10 else 75 if max_dd < 0.20 else 50 if max_dd < 0.30 else 25
    vol_score = 100 if vol < 0.12 else 75 if vol < 0.20 else 50 if vol < 0.30 else 25
    risk_score = (dd_score + vol_score) / 2
    dims.append({"name": "risk_control", "score": round(risk_score, 1),
                 "key": {"max_drawdown": analytics.get("max_drawdown", 0),
                         "volatility": vol}})

    # --- Risk Adjusted (weight 0.20) ---
    sharpe = analytics.get("sharpe_ratio", 0)
    sortino = analytics.get("sortino_ratio", 0)
    calmar = analytics.get("calmar_ratio", 0)
    adj_score = max(0, min(100, sharpe / 2.0 * 100))
    if sortino > 2.0:
        adj_score = min(100, adj_score + 5)
    if calmar > 1.5:
        adj_score = min(100, adj_score + 5)
    dims.append({"name": "risk_adjusted", "score": round(adj_score, 1),
                 "key": {"sharpe": sharpe, "sortino": sortino, "calmar": calmar}})

    # --- Trade Quality (weight 0.15) ---
    win_rate = analytics.get("win_rate_trade", 0)
    pl_ratio = analytics.get("profit_loss_ratio", 0)
    if pl_ratio == float("inf"):
        pl_ratio = 10.0
    trade_count = analytics.get("trade_count", 0)
    wr_score = max(0, min(100, win_rate / 0.70 * 100))
    pl_score = max(0, min(100, pl_ratio / 3.0 * 100))
    tc_score = 100 if trade_count >= 10 else 75 if trade_count >= 5 else 50
    trade_score = wr_score * 0.5 + pl_score * 0.3 + tc_score * 0.2
    dims.append({"name": "trade_quality", "score": round(trade_score, 1),
                 "key": {"win_rate": win_rate, "pl_ratio": pl_ratio,
                         "trade_count": trade_count}})

    # --- Excess Capability (weight 0.15) ---
    excess_ret = _finite_or(analytics.get("excess_return", 0))
    info_ratio = _finite_or(analytics.get("information_ratio", 0))
    bench_ret = _finite_or(analytics.get("benchmark_return", 0))
    bench_ref = abs(bench_ret) if abs(bench_ret) > 0.01 else 0.05
    excess_score = max(0, min(100, excess_ret / (bench_ref * 2.0) * 100))
    ir_bonus = max(0, min(10, info_ratio / 0.5 * 5))
    excess_score = min(100, excess_score + ir_bonus)
    dims.append({"name": "excess_capability", "score": round(excess_score, 1),
                 "key": {"excess_return": excess_ret, "info_ratio": info_ratio}})

    # --- Stability (weight 0.10) ---
    monthly_wr = 0.0
    mr = analytics.get("monthly_returns", {})
    if mr:
        positive_months = sum(1 for v in mr.values() if v > 0)
        monthly_wr = positive_months / len(mr)
    stab_score = max(0, min(100, monthly_wr / 0.80 * 100))
    dims.append({"name": "stability", "score": round(stab_score, 1),
                 "key": {"monthly_win_rate": round(monthly_wr, 3)}})

    # Overall weighted score
    weights = [0.20, 0.20, 0.20, 0.15, 0.15, 0.10]
    overall_score = sum(d["score"] * w for d, w in zip(dims, weights))

    def _grade(s):
        if s >= 85:
            return "S"
        if s >= 70:
            return "A"
        if s >= 55:
            return "B"
        if s >= 40:
            return "C"
        return "D"

    for d in dims:
        d["grade"] = _grade(d["score"])

    overall_grade = _grade(overall_score)
    weakest = min(dims, key=lambda d: d["score"])
    strongest = max(dims, key=lambda d: d["score"])

    summary_text = _build_summary_text(analytics, overall_grade, overall_score, dims, weakest)

    return {
        "overall": overall_grade,
        "score": round(overall_score, 1),
        "dimensions": dims,
        "weakest": weakest["name"],
        "strongest": strongest["name"],
        "summary_text": summary_text,
    }


def _build_summary_text(analytics, grade, score, dims, weakest):
    """Generate one-sentence strategy summary based on grade and metrics."""
    ann_ret = _finite_or(analytics.get("annual_return", 0))
    max_dd = _finite_or(analytics.get("max_drawdown", 0))
    sharpe = _finite_or(analytics.get("sharpe_ratio", 0))
    bench_raw = analytics.get("benchmark_return")
    excess_raw = analytics.get("excess_return")
    bench_known = (bench_raw is not None and np.isfinite(bench_raw)
                   and excess_raw is not None and np.isfinite(excess_raw))
    bench_ret = _finite_or(bench_raw)
    excess = _finite_or(excess_raw)

    if grade in ("S", "A"):
        prefix = "策略表现优异" if grade == "S" else "策略表现良好"
        body = (f"年化 {ann_ret:+.1%}，最大回撤 {max_dd:.1%}，"
                f"Sharpe {sharpe:.2f} 体现出色的风险调整收益")
        if bench_known and excess > 0:
            body += f"，超额收益 {excess:+.1%} 跑赢基准"
        return f"{prefix}：{body}。"
    elif grade == "B":
        return (f"策略表现中等：年化 {ann_ret:+.1%}，但回撤 {max_dd:.1%} 偏大。"
                f"Sharpe {sharpe:.2f}，建议关注{weakest['name']}维度。")
    else:
        if bench_known:
            beat = "跑赢" if excess > 0 else "未能跑赢"
            return (f"策略表现欠佳：年化 {ann_ret:+.1%} {beat}基准 ({bench_ret:+.1%})，"
                    f"最大回撤 {max_dd:.1%}。优先改善{weakest['name']}维度。")
        return (f"策略表现欠佳：年化 {ann_ret:+.1%}（基准数据不可用），"
                f"最大回撤 {max_dd:.1%}。优先改善{weakest['name']}维度。")


def diagnose_bottleneck(analytics, grade_info) -> list:
    """Identify failing metrics and root causes.

    Args:
        analytics: dict from analyze_returns()
        grade_info: dict from grade_strategy()

    Returns:
        list of diagnostic dicts with keys: metric, severity, finding,
        root_cause, affected_period, related_metrics.
    """
    if analytics is None or grade_info is None:
        return []

    diagnostics = []

    targets = {
        "sharpe_ratio": 1.0,
        "max_drawdown": -0.20,
        "annual_return": 0.0,
        "win_rate_trade": 0.40,
        "alpha": 0.0,
    }

    # Max drawdown check
    max_dd = analytics.get("max_drawdown", 0)
    if max_dd < targets["max_drawdown"]:
        dd_start = str(analytics.get("max_drawdown_start", ""))
        dd_end = str(analytics.get("max_drawdown_end", ""))
        per_stock = analytics.get("per_stock_pnl", {})
        worst_stock = min(per_stock.values()) if per_stock else 0
        consecutive_loss = 0
        max_consec = 0
        mr = analytics.get("monthly_returns", {})
        for v in mr.values():
            if v < 0:
                consecutive_loss += 1
                max_consec = max(max_consec, consecutive_loss)
            else:
                consecutive_loss = 0
        diagnostics.append({
            "metric": "max_drawdown",
            "severity": "critical" if max_dd < -0.25 else "warning",
            "finding": f"最大回撤 {max_dd:.1%} 超出 {abs(targets['max_drawdown']):.0%} 容忍线",
            "root_cause": "回撤期间未能及时减仓，单笔最大亏损占总资产比例过高",
            "affected_period": f"{dd_start} to {dd_end}",
            "related_metrics": {
                "worst_stock_pnl": round(worst_stock, 2),
                "max_consecutive_loss_months": max_consec,
                "max_loss_in_drawdown": round(max_dd, 4),
            },
        })

    # Sharpe check
    sharpe = analytics.get("sharpe_ratio", 0)
    if sharpe < targets["sharpe_ratio"]:
        diagnostics.append({
            "metric": "sharpe_ratio",
            "severity": "warning",
            "finding": f"Sharpe {sharpe:.2f} 低于 1.0 目标",
            "root_cause": "收益波动过大或收益率偏低，需优化入场信号或降低仓位波动",
            "affected_period": "full period",
            "related_metrics": {
                "annual_volatility": round(analytics.get("annual_volatility", 0), 4),
                "annual_return": round(analytics.get("annual_return", 0), 4),
            },
        })

    # Win rate check
    win_rate = analytics.get("win_rate_trade", 0)
    if analytics.get("trade_count", 0) >= 3 and win_rate < targets["win_rate_trade"]:
        diagnostics.append({
            "metric": "win_rate_trade",
            "severity": "warning",
            "finding": f"胜率 {win_rate:.0%} 低于 40% 目标",
            "root_cause": "入场信号质量不足，建议增加确认指标或收紧入场条件",
            "affected_period": "full period",
            "related_metrics": {
                "win_count": analytics.get("win_count", 0),
                "loss_count": analytics.get("loss_count", 0),
                "profit_loss_ratio": (
                    None if not np.isfinite(analytics.get("profit_loss_ratio", 0))
                    else round(analytics.get("profit_loss_ratio", 0), 2)
                ),
            },
        })

    # Alpha check — skipped when benchmark data was unavailable (NaN alpha)
    alpha_raw = analytics.get("alpha", 0)
    alpha_val = _finite_or(alpha_raw, default=float("nan"))
    if np.isfinite(alpha_val) and alpha_val < 0:
        diagnostics.append({
            "metric": "alpha",
            "severity": "warning",
            "finding": f"Alpha {alpha_val:+.2%} 为负，策略未能产生超额收益",
            "root_cause": "入场信号或持仓周期需优化，当前策略相对基准无信息优势",
            "affected_period": "full period",
            "related_metrics": {
                "beta": round(_finite_or(analytics.get("beta", 0)), 3),
                "excess_return": round(_finite_or(analytics.get("excess_return", 0)), 4),
            },
        })

    return diagnostics


def recommend_params(analytics, grade_info, current_params=None, param_ranges=None) -> list:
    """Suggest parameter adjustments based on diagnostics.

    Args:
        analytics: dict from analyze_returns()
        grade_info: dict from grade_strategy()
        current_params: dict of current PARAMS from strategy file (optional)
        param_ranges: dict of PARAM_RANGES from strategy file (optional)

    Returns:
        list of recommendation dicts with keys: priority, target_metric,
        action, parameter, current, suggested, range, rationale,
        expected_effect, risk.
    """
    if current_params is None or param_ranges is None:
        return []

    recommendations = []
    priority = 0

    max_dd = analytics.get("max_drawdown", 0) if analytics else 0
    sharpe = analytics.get("sharpe_ratio", 0) if analytics else 0
    win_rate = analytics.get("win_rate_trade", 0) if analytics else 0
    trade_count = analytics.get("trade_count", 0) if analytics else 0

    # Rule 1: Drawdown too large → tighten stop-loss
    if max_dd < -0.20 and "stop_loss_pct" in current_params and "stop_loss_pct" in param_ranges:
        priority += 1
        cur = current_params["stop_loss_pct"]
        lo, hi, step = param_ranges["stop_loss_pct"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "max_drawdown",
                "action": "decrease",
                "parameter": "stop_loss_pct",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": f"止损线从 {cur:.0%} 收紧至 {suggested:.0%}，在回撤早期截断亏损",
                "expected_effect": "max_drawdown 预计改善 3-5%",
                "risk": "可能增加止损触发频率，降低胜率 2-3%",
            })

    # Rule 2: Drawdown too large → reduce position size
    if max_dd < -0.20 and "position_pct" in current_params and "position_pct" in param_ranges:
        priority += 1
        cur = current_params["position_pct"]
        lo, hi, step = param_ranges["position_pct"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "max_drawdown",
                "action": "decrease",
                "parameter": "position_pct",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": f"单票仓位从 {cur:.0%} 降至 {suggested:.0%}，分散风险",
                "expected_effect": "max_drawdown 预计改善 4-6%",
                "risk": "收益绝对值会降低 2-4%",
            })

    # Rule 3: Sharpe too low → increase volatility confirmation
    if sharpe < 1.0 and "vol_confirm_mul" in current_params and "vol_confirm_mul" in param_ranges:
        priority += 1
        cur = current_params["vol_confirm_mul"]
        lo, hi, step = param_ranges["vol_confirm_mul"]
        suggested = min(hi, round(cur + step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "sharpe_ratio",
                "action": "increase",
                "parameter": "vol_confirm_mul",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "提高波动确认阈值，过滤低质量入场信号",
                "expected_effect": "Sharpe 预计提升 0.1-0.3",
                "risk": "交易次数可能减少",
            })

    # Rule 4: Win rate too low → widen RSI bands or tighten entry
    if win_rate < 0.40 and trade_count >= 3 and "rsi_oversold" in current_params and "rsi_oversold" in param_ranges:
        priority += 1
        cur = current_params["rsi_oversold"]
        lo, hi, step = param_ranges["rsi_oversold"]
        suggested = max(lo, round(cur - step))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "win_rate_trade",
                "action": "decrease",
                "parameter": "rsi_oversold",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "降低 RSI 超卖阈值，只在更极端的超卖区域入场",
                "expected_effect": "胜率预计提升 3-5%",
                "risk": "交易次数可能减少",
            })

    # Rule 5: Too few trades → decrease vol_confirm_mul
    if trade_count < 3 and "vol_confirm_mul" in current_params and "vol_confirm_mul" in param_ranges:
        priority += 1
        cur = current_params["vol_confirm_mul"]
        lo, hi, step = param_ranges["vol_confirm_mul"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "trade_count",
                "action": "decrease",
                "parameter": "vol_confirm_mul",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "降低波动确认倍数以产生更多交易信号",
                "expected_effect": "交易次数预计增加",
                "risk": "可能引入低质量交易",
            })

    return recommendations
