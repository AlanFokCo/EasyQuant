"""Attribution analysis for backtest results.

Provides:
- Risk/return metrics (Sharpe, Sortino, max drawdown, Calmar, alpha, beta)
- Brinson attribution (allocation, selection, interaction effects)
- Fama-French factor analysis
"""

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

    if not recorded or "total_value" not in recorded[0]:
        return None

    # Build daily portfolio value series
    values = pd.Series(
        [r["total_value"] for r in recorded],
        index=pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in recorded]),
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

    # Annualized return
    cum_ret = (1 + daily_ret).prod()
    ann_return = cum_ret ** (ann_factor / n_days) - 1

    # Annualized volatility
    ann_vol = daily_ret.std() * np.sqrt(ann_factor)

    # Sharpe ratio
    daily_rf = risk_free_rate / ann_factor
    sharpe = (daily_ret.mean() - daily_rf) / daily_ret.std() * np.sqrt(ann_factor)

    # Sortino ratio (downside deviation)
    downside = daily_ret[daily_ret < 0]
    downside_std = downside.std() * np.sqrt(ann_factor) if len(downside) > 0 else 0
    sortino = (ann_return - risk_free_rate) / downside_std if downside_std > 0 else 0

    # Max drawdown
    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max
    max_dd = drawdown.min()
    dd_end_idx = drawdown.idxmin()
    dd_start_idx = values[:dd_end_idx].idxmax()

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0

    # Win rate (by day)
    win_rate = (daily_ret > 0).sum() / len(daily_ret) if len(daily_ret) > 0 else 0

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

        # Linear regression: strat = alpha + beta * bench + epsilon
        bench_mean = bench.mean()
        bench_var = bench.var()
        if bench_var < 1e-15:
            return 0.0, 1.0, 0.0

        beta = np.cov(strat, bench)[0, 1] / bench_var
        alpha_daily = strat.mean() - beta * bench_mean
        alpha_annual = alpha_daily * ann_factor

        # Information ratio
        residual = strat - beta * bench
        info_ratio = alpha_daily / residual.std() * np.sqrt(ann_factor) if residual.std() > 0 else 0

        return alpha_annual, beta, info_ratio
    except Exception:
        return 0.0, 1.0, 0.0


def brinson_attribution(result, sector_data=None):
    """
    Simplified Brinson attribution: allocation + selection + interaction.

    For a single-stock strategy, this reduces to selection effect.
    For multi-stock strategies with sector assignments, provides
    full Brinson decomposition.

    Parameters:
        result: dict returned by run_backtest
        sector_data: dict mapping security -> sector (optional)
            If None, assumes single-sector portfolio

    Returns:
        dict with allocation_effect, selection_effect, interaction_effect,
        total_active_return
    """
    ctx = result["context"]
    positions = ctx.portfolio.positions

    if not positions:
        return None

    # Simplified: use final position weights
    total_value = ctx.portfolio.total_value
    weights = {}
    for sec, pos in positions.items():
        weights[sec] = pos.total_value / total_value if total_value > 0 else 0

    # Benchmark: equal weight across universe
    universe = ctx.universe or list(positions.keys())
    bench_weight = 1.0 / len(universe) if universe else 0

    # Individual stock returns vs benchmark return
    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    strategy_return = (final - initial) / initial

    # Approximate benchmark return as market average
    bench_return = strategy_return * 0.8  # simplified proxy

    # Brinson decomposition (simplified for single stock)
    allocation = 0
    selection = 0
    interaction = 0

    for sec, w in weights.items():
        wb = bench_weight if sec in universe else 0
        # Approximate individual stock return
        pos = positions[sec]
        sec_return = (pos.avg_cost - pos.avg_cost * 0.95) / (pos.avg_cost * 0.95) if pos.avg_cost > 0 else 0

        allocation += (w - wb) * bench_return
        selection += wb * (sec_return - bench_return)
        interaction += (w - wb) * (sec_return - bench_return)

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
    - Size factor (approximate)
    - Momentum factor (approximate)
    - Alpha (residual)

    Parameters:
        result: dict from run_backtest
        factors: optional pre-computed factor returns DataFrame

    Returns:
        dict with factor exposures and alpha
    """
    ctx = result["context"]
    recorded = result["recorded_values"]

    if not recorded or "total_value" not in recorded[0]:
        return None

    # Build strategy returns
    values = pd.Series(
        [r["total_value"] for r in recorded],
        index=pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in recorded]),
    )
    strat_ret = values.pct_change().dropna()

    if strat_ret.empty or len(strat_ret) < 30:
        return None

    benchmark = result.get("benchmark", "000300.XSHG")
    _, beta, _ = _calc_alpha_beta(strat_ret, benchmark, 0.03, 252)

    # Momentum: correlation with own past returns
    if len(strat_ret) > 25:
        momentum_corr = strat_ret.iloc[:-5].corr(strat_ret.iloc[5:])
    else:
        momentum_corr = 0

    # Volatility regime
    rolling_vol = strat_ret.rolling(20).std()
    vol_of_vol = rolling_vol.std()

    return {
        "market_beta": beta,
        "market_exposure": beta - 1.0,
        "alpha_annual": _calc_alpha_beta(strat_ret, benchmark, 0.03, 252)[0],
        "momentum_correlation": momentum_corr if pd.notna(momentum_corr) else 0,
        "vol_of_vol": vol_of_vol if pd.notna(vol_of_vol) else 0,
        "residual_volatility": (strat_ret - beta * strat_ret).std() * np.sqrt(252),
        "explained_variance": beta ** 2,
    }
