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
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR


def analyze_returns(result, risk_free_rate=RISK_FREE_RATE, trading_days=TRADING_DAYS_PER_YEAR):
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

    # Sortino ratio — semi-deviation of negative returns
    # Using ddof=1 (sample std) for consistency with Sharpe above.
    downside = daily_ret[daily_ret < 0]
    downside_std = downside.std() if len(downside) >= 2 else 0.0
    # Handle NaN from single-element downside series
    if pd.isna(downside_std) or downside_std <= 0:
        sortino = 0.0
    else:
        sortino = ((daily_ret.mean() - daily_rf) / downside_std * np.sqrt(ann_factor))
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

    # Benchmark comparison
    benchmark_name = result.get("benchmark", "000300.XSHG")
    alpha, beta, info_ratio, bench_daily_ret, bench_total_ret, bench_ann_vol = _calc_alpha_beta(
        daily_ret, benchmark_name, risk_free_rate, ann_factor
    )

    # Excess return metrics
    if bench_daily_ret is not None:
        excess_total, excess_max_dd, excess_sharpe, daily_excess_ret = _calc_excess_metrics(
            daily_ret, bench_daily_ret, risk_free_rate, ann_factor
        )
    else:
        excess_total = total_return - bench_total_ret if bench_total_ret is not None else 0.0
        excess_max_dd = 0.0
        excess_sharpe = 0.0
        daily_excess_ret = 0.0
        bench_total_ret = 0.0

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
    }


def _calc_trade_win_rate(trades):
    """Compute win rate by completed round-trip buy/sell pairs (item 12).

    Uses FIFO matching: each sell is matched against the oldest outstanding
    buy lot for that security.  A completed round trip is a "win" when the
    sell price exceeds the average buy cost of the matched shares.

    Returns:
        tuple: (win_rate, completed_trade_count, win_count, loss_count)
    """
    from collections import deque

    buy_queues: dict = {}    # security -> deque of (price, amount) lots
    wins = 0
    losses = 0
    total = 0

    for trade in trades:
        sec = trade["security"]
        t_type = trade.get("type")
        if t_type not in ("BUY", "SELL"):
            continue
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
                else:
                    losses += 1

    win_rate = wins / total if total > 0 else 0.0
    return win_rate, total, wins, losses


def _calc_profit_loss_ratio(trades):
    """Compute avg win / avg loss from FIFO-matched trade pairs.

    For each completed round-trip, compute the total P&L in yuan
    (sell_proceeds - buy_cost).  Then separate wins and losses,
    compute their averages, and return the ratio.

    Returns:
        tuple: (profit_loss_ratio, win_count, loss_count)
               profit_loss_ratio = avg_win / abs(avg_loss), or 0.0 if no losses.
    """
    from collections import deque

    buy_queues: dict = {}
    win_pnls = []
    loss_pnls = []

    for trade in trades:
        sec = trade["security"]
        t_type = trade.get("type")
        if t_type not in ("BUY", "SELL"):
            continue
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
                pnl = (price - avg_buy) * total_matched
                if pnl > 0:
                    win_pnls.append(pnl)
                else:
                    loss_pnls.append(pnl)

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


def _calc_alpha_beta(strategy_returns, benchmark_code, rf_rate, ann_factor):
    """Calculate alpha, beta, information ratio vs benchmark, plus benchmark series.

    Requires at least 10 overlapping trading days between the strategy and the
    benchmark return series.  When fewer data points are available this function
    returns ``(0.0, 1.0, 0.0, None, 0.0, 0.0)`` as safe defaults.

    Returns:
        tuple: (alpha_annual, beta, info_ratio, benchmark_daily_ret,
                benchmark_total_return, benchmark_annual_volatility)
    """
    default = (0.0, 1.0, 0.0, None, 0.0, 0.0)
    try:
        from eqlib.data import fetch_stock_data

        start = strategy_returns.index[0] - datetime.timedelta(days=30)
        end = strategy_returns.index[-1]

        bench_df = fetch_stock_data(benchmark_code, start, end)
        if bench_df.empty or "close" not in bench_df.columns:
            return default

        bench_ret = bench_df["close"].pct_change().dropna()

        # Use the intersection of dates — fillna(0) would treat missing days
        # as "benchmark returned 0%" which biases beta low and alpha high.
        common = strategy_returns.index.intersection(bench_ret.index)
        strat = strategy_returns.loc[common].values
        bench = bench_ret.loc[common].values

        if len(strat) < 10:
            return default

        cov_matrix = np.cov(strat, bench, ddof=1)
        # Handle NaN in covariance matrix (can occur with NaN inputs)
        if not np.isfinite(cov_matrix).all():
            return default
        bench_var = cov_matrix[1, 1]
        if bench_var < 1e-15:
            return default

        beta = cov_matrix[0, 1] / bench_var
        alpha_daily = strat.mean() - beta * bench.mean()
        alpha_annual = alpha_daily * ann_factor

        active = strat - bench
        active_mean = active.mean()
        active_std = active.std(ddof=1)
        info_ratio = (active_mean / active_std * np.sqrt(ann_factor)
                      if active_std > 0 else 0.0)

        # Benchmark total and annualized volatility
        bench_daily_ret = pd.Series(bench, index=common)
        bench_total_ret = float((1 + bench_daily_ret).prod() - 1)
        bench_ann_vol = float(bench_daily_ret.std() * np.sqrt(ann_factor))

        return alpha_annual, beta, info_ratio, bench_daily_ret, bench_total_ret, bench_ann_vol
    except Exception:
        return default


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
    alpha_annual, beta, _, _, _, _ = _calc_alpha_beta(strat_ret, benchmark, 0.03, 252)

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
