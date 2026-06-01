"""Portfolio optimization utilities.

Provides mathematical optimization for asset allocation:
- Minimum variance
- Maximum Sharpe ratio
- Equal risk contribution (risk parity)
"""

import numpy as np
import pandas as pd
from eqlib.constants import RISK_FREE_RATE


class Bound:
    """Weight bounds for a single asset."""

    def __init__(self, lower=0.0, upper=1.0):
        self.lower = lower
        self.upper = upper


class MinVariance:
    """Target: minimize portfolio variance."""
    name = "min_variance"


class MaxSharpe:
    """Target: maximize Sharpe ratio.

    Parameters:
        risk_free_rate: annualized risk-free rate used in the Sharpe
            denominator (default 0.03 = 3%, consistent with typical
            Chinese government bond yields).  Ensure this matches the
            risk-free rate used elsewhere in the backtest (e.g. in
            ``analyze_returns``).
    """
    name = "max_sharpe"

    def __init__(self, risk_free_rate=RISK_FREE_RATE):
        self.risk_free_rate = risk_free_rate


class RiskParity:
    """Target: equal risk contribution across assets."""
    name = "risk_parity"


def _get_returns(prices, days=250):
    """Convert price DataFrame to daily returns matrix."""
    ret = prices.pct_change().dropna().tail(days)
    return ret


def _annual_stats(weights, returns, days=252):
    """Calculate annualized return, volatility, and Sharpe for a weight vector.

    Annualized return uses the geometric (compound) formula instead of the
    arithmetic approximation ``mean * days``, which significantly overestimates
    returns at high volatility.
    """
    port_ret = returns.dot(weights)
    n = len(port_ret)
    # Geometric annualization: avoids over-estimation at high vol
    ann_ret = (1 + port_ret).prod() ** (days / n) - 1 if n > 0 else 0.0
    ann_vol = port_ret.std() * np.sqrt(days)
    return ann_ret, ann_vol


def _ledoit_wolf_cov(returns: pd.DataFrame) -> np.ndarray:
    """Compute a Ledoit-Wolf shrinkage covariance matrix.

    Replaces the raw sample covariance matrix with a better-conditioned
    shrinkage estimate.  When ``sklearn`` is available, its analytically
    optimal shrinkage coefficient is used; otherwise falls back to the Oracle
    Approximating Shrinkage (OAS) estimator from a manual implementation,
    or ultimately to the plain sample covariance.

    This reduces optimization instability when the number of observations
    is small relative to the number of assets.
    """
    X = returns.values
    try:
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf()
        lw.fit(X)
        return lw.covariance_
    except ImportError:
        pass

    # Manual Ledoit-Wolf (Oracle Approximating Shrinkage)
    n, p = X.shape
    if n < 2 or p < 2:
        import warnings
        warnings.warn(
            "LedoitWolf fallback: sample covariance used (n<2 or p<2 — matrix may be ill-conditioned).",
            UserWarning, stacklevel=2,
        )
        return np.cov(X, rowvar=False)

    sample_cov = np.cov(X, rowvar=False)
    mu = np.trace(sample_cov) / p
    target = mu * np.eye(p)

    # Shrinkage intensity
    X_centered = X - X.mean(axis=0)
    delta_sq = np.linalg.norm(sample_cov - target, "fro") ** 2
    beta_sq_num = sum(
        np.linalg.norm(
            np.outer(X_centered[i], X_centered[i]) - sample_cov, "fro"
        ) ** 2
        for i in range(n)
    ) / (n ** 2)
    rho = min(beta_sq_num / delta_sq, 1.0) if delta_sq > 0 else 0.0

    return (1.0 - rho) * sample_cov + rho * target


def portfolio_optimizer(securities, prices, target=None, constraints=None,
                        bounds=None, default_range=(0.0, 1.0),
                        ftol=1e-9, return_none_if_fail=True):
    """
    Optimize portfolio weights under given constraints.

    Parameters:
        securities: list of stock codes
        prices: DataFrame of prices, columns=securities, index=date
        target: optimization objective
            - MinVariance(): minimize portfolio variance
            - MaxSharpe(risk_free_rate): maximize Sharpe ratio
            - RiskParity(): equal risk contribution
            Default: MinVariance
        constraints: dict with optional keys:
            - max_weight: maximum weight for any single asset (default 1.0)
            - min_weight: minimum weight for any single asset (default 0.0)
            - max_assets: limit number of non-zero assets (not enforced, soft)
        bounds: list of Bound objects, one per security
            Default: same bounds for all assets from default_range
        default_range: (min, max) weight range when bounds is None
        ftol: optimization tolerance
        return_none_if_fail: return None on failure instead of raising

    Returns:
        pd.Series of optimized weights (security -> weight), or None on failure
    """
    from scipy.optimize import minimize

    if target is None:
        target = MinVariance()

    returns = _get_returns(prices, days=250)
    if returns.empty or len(returns) < 20:
        return None

    securities = [s for s in securities if s in returns.columns]
    if len(securities) < 2:
        return None

    returns = returns[securities]

    # ── Ledoit-Wolf covariance shrinkage (item 19) ─────────────────────────
    # Replaces the raw sample covariance matrix with a better-conditioned
    # shrinkage estimate, which significantly reduces optimization instability
    # when the number of observations is small relative to the number of assets.
    cov = _ledoit_wolf_cov(returns)
    n = len(securities)

    # Build bounds
    if bounds is None:
        min_w = constraints.get("min_weight", 0.0) if constraints else 0.0
        max_w = constraints.get("max_weight", 1.0) if constraints else 1.0
        bounds = [(min_w, max_w)] * n
    else:
        bounds = [(b.lower, b.upper) if isinstance(b, Bound) else b for b in bounds]

    # Initial weights: equal
    w0 = np.array([1.0 / n] * n)

    # Sum-to-one constraint
    eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    try:
        if isinstance(target, MinVariance):
            def objective(w):
                return w @ cov @ w

            res = minimize(objective, w0, method="SLSQP",
                           bounds=bounds, constraints=eq_constraint,
                           options={"ftol": ftol, "maxiter": 1000})

        elif isinstance(target, MaxSharpe):
            rf = getattr(target, "risk_free_rate", 0.03)

            def neg_sharpe(w):
                ret, vol = _annual_stats(w, returns, days=252)
                if vol < 1e-10:
                    return 1e10   # large penalty pushes optimizer away
                return -(ret - rf) / vol

            res = minimize(neg_sharpe, w0, method="SLSQP",
                           bounds=bounds, constraints=eq_constraint,
                           options={"ftol": ftol, "maxiter": 1000})

        elif isinstance(target, RiskParity):
            # Risk parity: minimize sum of (risk_contrib_i - target)^2
            def risk_parity_obj(w):
                w = np.maximum(w, 1e-10)
                sigma = np.sqrt(w @ cov @ w)
                marginal_risk = cov @ w
                risk_contrib = w * marginal_risk / sigma
                target_rc = sigma / n
                return np.sum((risk_contrib - target_rc) ** 2)

            res = minimize(risk_parity_obj, w0, method="SLSQP",
                           bounds=bounds, constraints=eq_constraint,
                           options={"ftol": ftol, "maxiter": 1000})
        else:
            return None

        if res.success:
            weights = res.x
            # Zero out tiny weights
            weights[np.abs(weights) < 1e-6] = 0
            total = weights.sum()
            if total <= 0:
                # All weights zeroed out — cannot normalize
                return None
            # Normalize to sum to 1
            weights = weights / total
            # D4: Iteratively clip weights to max_weight and renormalize
            max_w = constraints.get("max_weight", 1.0) if constraints else 1.0
            for _ in range(20):  # prevent infinite loop
                if np.all(weights <= max_w + 1e-9):
                    break
                weights = np.minimum(weights, max_w)
                total = weights.sum()
                if total <= 0:
                    return None
                weights = weights / total
            return pd.Series(weights, index=securities)

        if return_none_if_fail:
            return None
        raise RuntimeError(f"Optimization failed: {res.message}")

    except Exception:
        if return_none_if_fail:
            return None
        raise
