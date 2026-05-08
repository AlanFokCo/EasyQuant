"""Attribution analysis for backtest results.

Provides:
- Risk/return metrics (Sharpe, Sortino, max drawdown, Calmar, alpha, beta)
- Trade-level win rate (matched round-trip buy/sell pairs)
- Turnover and total commission cost metrics
- Brinson attribution (allocation, selection, interaction effects)
  with optional real benchmark_returns Series
- Fama-French factor analysis
"""

import datetime
import numpy as np
import pandas as pd


def analyze_returns(result, risk_free_rate=0.03, trading_days=252):
    """Calculate comprehensive risk and return metrics from a backtest result.

    Parameters:
        result: dict returned by run_backtest or run_strategy
        risk_free_rate: annual risk-free rate (default 0.03)
        trading_days: number of trading days per year (default 252)

    Returns:
        dict with metrics including:
            total_return, annual_return, annual_volatility, sharpe_ratio,
            sortino_ratio, max_drawdown, calmar_ratio, alpha, beta,
            information_ratio,
            win_rate_daily: daily win rate (fraction of profitable days),
            win_rate_trade: round-trip trade win rate (matched buy/sell pairs),
            trade_count: number of completed round-trip trades,
            annual_turnover: total traded value / avg portfolio value / years,
            total_commission: sum of all commissions paid,
            net_return: total return after deducting all commissions.
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
    sharpe = (daily_ret.mean() - daily_rf) / std * np.sqrt(ann_factor) if std > 0 else 0.0

    # Sortino ratio
    downside = daily_ret[daily_ret < daily_rf]
    downside_std = downside.std(ddof=1) if len(downside) >= 2 else 0.0
    sortino = ((daily_ret.mean() - daily_rf) / downside_std * np.sqrt(ann_factor)
               if downside_std > 0 else 0.0)

    # Max drawdown
    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max
    max_dd = drawdown.min()
    dd_end_idx = drawdown.idxmin()
    peak_slice = values[:dd_end_idx]
    dd_start_idx = peak_slice.idxmax() if not peak_slice.empty else values.index[0]

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # Win rate (by day)
    win_rate_daily = float((daily_ret > 0).sum()) / n_days

    # ── Trade-level win rate (item 12) ────────────────────────────────────
    win_rate_trade, trade_count = _calc_trade_win_rate(trades)

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
    annual_turnover = (min(total_buy_value, total_sell_value) / avg_portfolio_value / years
                       if avg_portfolio_value > 0 and years > 0 else 0.0)
    total_commission = sum(t.get("commission", 0.0) for t in trades)
    net_return = total_return - total_commission / initial

    # Benchmark comparison
    benchmark_name = result.get("benchmark", "000300.XSHG")
    alpha, beta, info_ratio = _calc_alpha_beta(
        daily_ret, benchmark_name, risk_free_rate, ann_factor
    )

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
        "annual_turnover": annual_turnover,
        "total_commission": total_commission,
        "net_return": net_return,
        "trading_days": n_days,
        "num_trades": len(trades),
    }


def _calc_trade_win_rate(trades):
    """Compute win rate by completed round-trip buy/sell pairs (item 12).

    Uses FIFO matching: each sell is matched against the oldest outstanding
    buy lot for that security.  A completed round trip is a "win" when the
    sell price exceeds the average buy cost of the matched shares.

    Returns:
        tuple: (win_rate, completed_trade_count)
    """
    from collections import deque

    buy_queues: dict = {}    # security -> deque of (price, amount) lots
    wins = 0
    total = 0

    for trade in trades:
        sec = trade["security"]
        t_type = trade.get("type")
        price = trade["price"]
        amount = trade["amount"]

        if t_type == "BUY":
            buy_queues.setdefault(sec, deque()).append((price, amount))

        elif t_type == "SELL":
            remaining = amount
            q = buy_queues.get(sec, deque())
            total_buy_cost = 0.0
            total_matched = 0

            while remaining > 0 and q:
                buy_price, buy_amt = q[0]
                matched = min(buy_amt, remaining)
                total_buy_cost += buy_price * matched
                total_matched += matched
                remaining -= matched
                if matched == buy_amt:
                    q.popleft()
                else:
                    q[0] = (buy_price, buy_amt - matched)

            if total_matched > 0:
                avg_buy = total_buy_cost / total_matched
                total += 1
                if price > avg_buy:
                    wins += 1

    win_rate = wins / total if total > 0 else 0.0
    return win_rate, total


def _calc_alpha_beta(strategy_returns, benchmark_code, rf_rate, ann_factor):
    """Calculate alpha, beta, and information ratio vs benchmark.

    Requires at least 10 overlapping trading days between the strategy and the
    benchmark return series.  When fewer data points are available this function
    returns ``(0.0, 1.0, 0.0)`` as safe defaults — callers should not interpret
    these as meaningful estimates.
    """
    try:
        from eqlib.data import fetch_stock_data

        start = strategy_returns.index[0] - datetime.timedelta(days=30)
        end = strategy_returns.index[-1]

        bench_df = fetch_stock_data(benchmark_code, start, end)
        if bench_df.empty or "close" not in bench_df.columns:
            return 0.0, 1.0, 0.0

        bench_ret = bench_df["close"].pct_change().dropna()
        bench_ret = bench_ret.reindex(strategy_returns.index).fillna(0)

        common = strategy_returns.index.intersection(bench_ret.index)
        strat = strategy_returns.loc[common].values
        bench = bench_ret.loc[common].values

        if len(strat) < 10:
            return 0.0, 1.0, 0.0

        cov_matrix = np.cov(strat, bench, ddof=1)
        bench_var = cov_matrix[1, 1]
        if bench_var < 1e-15:
            return 0.0, 1.0, 0.0

        beta = cov_matrix[0, 1] / bench_var
        alpha_daily = strat.mean() - beta * bench.mean()
        alpha_annual = alpha_daily * ann_factor

        active = strat - bench
        active_mean = active.mean()
        active_std = active.std(ddof=1)
        info_ratio = (active_mean / active_std * np.sqrt(ann_factor)
                      if active_std > 0 else 0.0)

        return alpha_annual, beta, info_ratio
    except Exception:
        return 0.0, 1.0, 0.0


def brinson_attribution(result, sector_data=None, benchmark_returns=None):
    """Brinson attribution: allocation + selection + interaction effects.

    Parameters:
        result: dict returned by run_backtest
        sector_data: dict mapping security -> sector (optional)
        benchmark_returns: optional pd.Series with benchmark daily returns
            indexed by date, used for realistic benchmark comparison.
            When None, falls back to an equal-weight universe approximation.

    Returns:
        dict with allocation_effect, selection_effect, interaction_effect,
        total_active_return; or None if no trades or positions exist.
    """
    ctx = result["context"]
    trade_log = result.get("trade_log", [])
    positions = ctx.portfolio.positions

    if not trade_log and not positions:
        return None

    total_value = ctx.portfolio.total_value
    if total_value <= 0:
        return None

    # Compute per-security returns from trade log + final open positions
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

    # ── Benchmark return (item 14) ────────────────────────────────────────
    # Use caller-supplied benchmark_returns if available, otherwise fall back
    # to the equal-weight universe approximation.
    if benchmark_returns is not None and isinstance(benchmark_returns, pd.Series):
        bench_return = float((1 + benchmark_returns).prod() - 1)
        bench_weight = 1.0 / len(all_secs) if all_secs else 0.0
    else:
        universe = ctx.universe or sorted(all_secs)
        bench_weight = 1.0 / len(universe) if universe else 0.0
        bench_return = (
            sum(sec_returns.get(s, 0.0) for s in universe) / len(universe)
            if universe else 0.0
        )

    allocation = 0.0
    selection = 0.0
    interaction = 0.0

    universe_set = set(ctx.universe or all_secs)
    for sec in all_secs:
        w = weights.get(sec, 0.0)
        wb = bench_weight if sec in universe_set else 0.0
        r_sec = sec_returns.get(sec, 0.0)

        allocation += (w - wb) * bench_return
        selection += wb * (r_sec - bench_return)
        interaction += (w - wb) * (r_sec - bench_return)

    return {
        "allocation_effect": allocation,
        "selection_effect": selection,
        "interaction_effect": interaction,
        "total_active_return": allocation + selection + interaction,
    }


def fama_french_analysis(result, factors=None):
    """Simplified factor analysis (not a full Fama-French 3-factor model).

    Decomposes strategy returns into:
    - Market factor (beta vs benchmark)
    - Momentum proxy (lag-5 return autocorrelation, not a true UMD factor)
    - Alpha (residual vs market)

    Note: This function does **not** implement the true Fama-French 3-factor
    model (Fama & French, 1993), which requires SMB and HML factor data.
    The ``momentum_correlation`` field is a return autocorrelation, not a
    genuine momentum factor exposure.

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
    alpha_annual, beta, _ = _calc_alpha_beta(strat_ret, benchmark, 0.03, 252)

    arr = strat_ret.values
    if len(arr) > 10:
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
            bench_ret = bench_ret.reindex(strat_ret.index).fillna(0)
            common = strat_ret.index.intersection(bench_ret.index)
            s = strat_ret.loc[common].values
            b = bench_ret.loc[common].values
            if len(s) > 1:
                residual = s - beta * b
                residual_vol = float(residual.std(ddof=1)) * np.sqrt(252)
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
