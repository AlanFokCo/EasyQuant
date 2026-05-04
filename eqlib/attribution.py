"""Attribution analysis for backtest results.

Provides:
- Risk/return metrics (Sharpe, Sortino, max drawdown, Calmar, alpha, beta)
- Brinson attribution (allocation, selection, interaction effects)
- Fama-French factor analysis
"""

import datetime
import numpy as np
import pandas as pd


def analyze_returns(result, risk_free_rate=0.03, trading_days=252):
    """
    Calculate comprehensive risk and return metrics from a backtest result.

    Parameters:
        result: dict returned by run_backtest or run_strategy
        risk_free_rate: annual risk-free rate (default 0.03)
        trading_days: number of trading days per year (default 252)

    Returns:
        dict with metrics:
            total_return, annual_return, annual_volatility, sharpe_ratio,
            sortino_ratio, max_drawdown, max_drawdown_start, max_drawdown_end,
            calmar_ratio, alpha, beta, information_ratio, win_rate
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

    # Sharpe ratio — guard against zero volatility
    daily_rf = risk_free_rate / ann_factor
    sharpe = (daily_ret.mean() - daily_rf) / std * np.sqrt(ann_factor) if std > 0 else 0.0

    # Sortino ratio — require at least 2 downside observations for a stable
    # sample std (ddof=1); fewer observations produce an unreliable estimate.
    downside = daily_ret[daily_ret < 0]
    downside_std = downside.std(ddof=1) * np.sqrt(ann_factor) if len(downside) >= 2 else 0.0
    sortino = (ann_return - risk_free_rate) / downside_std if downside_std > 0 else 0.0

    # Max drawdown
    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max
    max_dd = drawdown.min()
    dd_end_idx = drawdown.idxmin()
    # Guard against empty peak slice (drawdown starts at first bar)
    peak_slice = values[:dd_end_idx]
    dd_start_idx = peak_slice.idxmax() if not peak_slice.empty else values.index[0]

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # Win rate (by day)
    win_rate = float((daily_ret > 0).sum()) / n_days

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
        "win_rate": win_rate,
        "trading_days": n_days,
        "num_trades": len(trades),
    }


def _calc_alpha_beta(strategy_returns, benchmark_code, rf_rate, ann_factor):
    """Calculate alpha, beta, and information ratio vs benchmark."""
    try:
        from eqlib.data import fetch_stock_data
        import datetime

        # Fetch 30 extra days before the strategy start so the benchmark
        # pct_change() series covers the full strategy return window after dropna().
        start = strategy_returns.index[0] - datetime.timedelta(days=30)
        end = strategy_returns.index[-1]

        bench_df = fetch_stock_data(benchmark_code, start, end)
        if bench_df.empty or "close" not in bench_df.columns:
            return 0.0, 1.0, 0.0

        bench_ret = bench_df["close"].pct_change().dropna()
        bench_ret = bench_ret.reindex(strategy_returns.index).fillna(0)

        # Align
        common = strategy_returns.index.intersection(bench_ret.index)
        strat = strategy_returns.loc[common].values
        bench = bench_ret.loc[common].values

        if len(strat) < 10:
            return 0.0, 1.0, 0.0

        # Use np.cov with ddof=1 so covariance and variance are both sample
        # estimates — cov_matrix[0,1] is cov(strat,bench),
        # cov_matrix[1,1] is var(bench).
        cov_matrix = np.cov(strat, bench, ddof=1)
        bench_var = cov_matrix[1, 1]
        if bench_var < 1e-15:
            return 0.0, 1.0, 0.0

        beta = cov_matrix[0, 1] / bench_var
        alpha_daily = strat.mean() - beta * bench.mean()
        alpha_annual = alpha_daily * ann_factor

        # Information ratio: annualized alpha / annualized tracking error
        residual = strat - beta * bench
        residual_std = residual.std(ddof=1)
        info_ratio = alpha_daily / residual_std * np.sqrt(ann_factor) if residual_std > 0 else 0.0

        return alpha_annual, beta, info_ratio
    except Exception:
        return 0.0, 1.0, 0.0


def brinson_attribution(result, sector_data=None):
    """
    Brinson attribution: allocation + selection + interaction effects.

    Per-security returns are derived from the trade log (realized proceeds
    plus remaining open-position market value vs total buy cost), giving
    accurate attribution rather than a hardcoded proxy.

    For single-stock strategies this reduces to selection effect.
    For multi-stock strategies with sector assignments, provides
    full Brinson decomposition.

    Parameters:
        result: dict returned by run_backtest
        sector_data: dict mapping security -> sector (optional)
            If None, assumes single-sector portfolio

    Returns:
        dict with allocation_effect, selection_effect, interaction_effect,
        total_active_return, or None if no trades or positions exist
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

    # Final portfolio weights by open-position market value
    weights = {
        sec: pos.total_value / total_value
        for sec, pos in positions.items()
    }

    # Benchmark: equal weight across strategy universe
    universe = ctx.universe or sorted(all_secs)
    bench_weight = 1.0 / len(universe) if universe else 0.0

    # Benchmark return: equal-weighted average of individual security returns
    bench_return = (
        sum(sec_returns.get(s, 0.0) for s in universe) / len(universe)
        if universe else 0.0
    )

    allocation = 0.0
    selection = 0.0
    interaction = 0.0

    for sec in all_secs:
        w = weights.get(sec, 0.0)
        wb = bench_weight if sec in universe else 0.0
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
    """
    Simplified Fama-French style factor analysis.

    Decomposes strategy returns into:
    - Market factor (beta)
    - Momentum factor (lag-5 autocorrelation)
    - Alpha (residual)

    Parameters:
        result: dict from run_backtest
        factors: optional pre-computed factor returns DataFrame

    Returns:
        dict with factor exposures and alpha
    """
    recorded = result["recorded_values"]

    if not recorded:
        return None

    # Build strategy returns
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

    # Momentum: lag-5 autocorrelation of daily returns.
    # Lag 5 (one trading week) is a conventional short-term momentum window
    # that captures weekly serial correlation in equity returns.
    # `.values` is used to avoid DatetimeIndex misalignment.
    arr = strat_ret.values
    if len(arr) > 10:
        momentum_corr = float(np.corrcoef(arr[:-5], arr[5:])[0, 1])
        if not np.isfinite(momentum_corr):
            momentum_corr = 0.0
    else:
        momentum_corr = 0.0

    # Volatility regime
    rolling_vol = strat_ret.rolling(20).std()
    vol_of_vol = float(rolling_vol.std()) if not rolling_vol.dropna().empty else 0.0

    # Residual volatility and R² using actual benchmark returns
    residual_vol = 0.0
    explained_var = 0.0
    try:
        from eqlib.data import fetch_stock_data
        import datetime

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
                # R² = 1 - var(residual) / var(strat)
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
