"""Money management and position sizing calculations.

Provides:
- Kelly Criterion
- Fixed fractional / Fixed ratio sizing
- Percent-of-equity sizing
- Risk-based sizing (stop-loss distance)
- Volatility-targeting sizing
"""

import numpy as np
import pandas as pd


# ============================================================
# Kelly Criterion
# ============================================================

def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly Criterion: optimal fraction of capital to bet.

    Parameters:
        win_rate: probability of winning (0-1)
        avg_win: average profit per winning trade
        avg_loss: average loss per losing trade (positive number)

    Returns:
        Fraction of capital (0-1). Negative means no bet.
    """
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss  # win/loss ratio
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    return max(kelly, 0.0)


def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly: more conservative version."""
    return kelly_criterion(win_rate, avg_win, avg_loss) * 0.5


def kelly_from_returns(returns: pd.Series) -> float:
    """Kelly from a series of trade returns.

    Separates wins and losses to compute win rate and avg win/loss.
    """
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(returns) if len(returns) > 0 else 0
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    return kelly_criterion(win_rate, avg_win, avg_loss)


# ============================================================
# Fixed Sizing
# ============================================================

def fixed_fraction_size(capital: float, risk_pct: float,
                        entry_price: float, stop_price: float) -> int:
    """Position size by fixed fractional risk.

    Limits risk to risk_pct of capital based on stop-loss distance.

    Parameters:
        capital: total account value
        risk_pct: fraction of capital to risk (e.g., 0.02 = 2%)
        entry_price: planned entry price
        stop_price: stop-loss price

    Returns:
        Number of shares (rounded down).
    """
    risk_amount = capital * risk_pct
    loss_per_share = abs(entry_price - stop_price)
    if loss_per_share <= 0:
        return 0
    shares = int(risk_amount / loss_per_share // 100) * 100
    return max(shares, 0)


def fixed_ratio_size(capital: float, equity_ratio: float,
                     entry_price: float) -> int:
    """Position size by fixed ratio of equity.

    Parameters:
        capital: total account value
        equity_ratio: fraction of capital to allocate (e.g., 0.1 = 10%)
        entry_price: planned entry price

    Returns:
        Number of shares (rounded down to lot size).
    """
    allocation = capital * equity_ratio
    shares = int(allocation / entry_price // 100) * 100
    return max(shares, 0)


def percent_of_equity(capital: float, pct: float) -> float:
    """Calculate dollar amount for a percentage of equity."""
    return capital * pct


# ============================================================
# Volatility Targeting
# ============================================================

def volatility_target_size(capital: float, target_vol: float,
                           price: float, vol_per_share: float) -> int:
    """Position size to achieve target portfolio volatility.

    Parameters:
        capital: total account value
        target_vol: target portfolio volatility (e.g., 0.15 = 15%)
        price: current price
        vol_per_share: volatility per share (absolute dollar volatility)

    Returns:
        Number of shares.
    """
    if vol_per_share <= 0 or price <= 0:
        return 0
    target_value = capital * target_vol / vol_per_share
    shares = int(target_value / price // 100) * 100
    return max(shares, 0)


def atr_position_size(capital: float, risk_pct: float,
                      atr: float, n_atr: float = 2.0) -> int:
    """Position size based on ATR (Average True Range).

    Risk = risk_pct of capital, stop distance = n_atr * ATR.

    Parameters:
        capital: total account value
        risk_pct: fraction of capital to risk
        atr: current ATR value
        n_atr: number of ATR multiples for stop

    Returns:
        Number of shares.
    """
    stop_distance = atr * n_atr
    if stop_distance <= 0:
        return 0
    risk_amount = capital * risk_pct
    shares = int(risk_amount / stop_distance // 100) * 100
    return max(shares, 0)


# ============================================================
# Anti-Martingale / Martingale
# ============================================================

def martingale_size(base_amount: int, loss_streak: int,
                    multiplier: float = 2.0) -> int:
    """Martingale: double size after each loss.

    Parameters:
        base_amount: initial trade size
        loss_streak: number of consecutive losses
        multiplier: sizing multiplier (default 2)

    Returns:
        New trade size.
    """
    return int(base_amount * (multiplier ** loss_streak))


def anti_martingale_size(base_amount: int, win_streak: int,
                         multiplier: float = 1.5) -> int:
    """Anti-Martingale: increase size after wins.

    Parameters:
        base_amount: initial trade size
        win_streak: number of consecutive wins
        multiplier: sizing multiplier (default 1.5)

    Returns:
        New trade size.
    """
    return int(base_amount * (multiplier ** win_streak))


# ============================================================
# Portfolio Weight Helpers
# ============================================================

def equal_weight(n: int) -> list[float]:
    """Equal weight for n assets."""
    if n <= 0:
        return []
    w = 1.0 / n
    return [w] * n


def risk_parity_weights(volatilities: list[float]) -> list[float]:
    """Approximate risk parity weights (inverse volatility).

    Each asset contributes equally to portfolio risk.
    """
    inv_vol = [1.0 / v if v > 0 else 0 for v in volatilities]
    total = sum(inv_vol)
    if total == 0:
        return equal_weight(len(volatilities))
    return [w / total for w in inv_vol]


def volatility_normalize(returns: pd.Series) -> pd.Series:
    """Normalize returns by rolling volatility (vol-targeting).

    Scales returns so that each period has unit volatility.
    Useful for comparing strategies across regimes.
    """
    vol = returns.rolling(20).std()
    return returns / vol.replace(0, np.nan)
