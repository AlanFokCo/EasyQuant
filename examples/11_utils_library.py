"""Example 11: Using the utils library.

Demonstrates technical indicators, statistical utilities,
and money management calculations available in eqlib.utils.
"""

from eqlib import *
import pandas as pd
import numpy as np

# Generate sample price data for demonstration
np.random.seed(42)
dates = pd.date_range("2024-01-01", periods=100, freq="B")
close = pd.Series(
    10.0 * np.cumprod(1 + np.random.normal(0.001, 0.02, 100)),
    index=dates,
)
high = close * (1 + np.abs(np.random.normal(0, 0.01, 100)))
low = close * (1 - np.abs(np.random.normal(0, 0.01, 100)))
volume = pd.Series(np.random.randint(10000, 100000, 100), index=dates)


# ============================================================
# 1. Technical Indicators
# ============================================================

print("=" * 50)
print("1. Technical Indicators")
print("=" * 50)

# Moving Averages
ma5 = utils.ma(close, 5)
ema10 = utils.ema(close, 10)
print(f"MA(5)  latest: {ma5.iloc[-1]:.3f}")
print(f"EMA(10) latest: {ema10.iloc[-1]:.3f}")

# MACD
dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
print(f"\nMACD(12,26,9):")
print(f"  DIF: {dif.iloc[-1]:.4f}")
print(f"  DEA: {dea.iloc[-1]:.4f}")
print(f"  Hist: {hist.iloc[-1]:.4f}")

# RSI
rsi14 = utils.rsi(close, 14)
print(f"\nRSI(14): {rsi14.iloc[-1]:.1f}")

# KDJ
k, d, j = utils.kdj(high, low, close, period=9)
print(f"\nKDJ(9): K={k.iloc[-1]:.1f}, D={d.iloc[-1]:.1f}, J={j.iloc[-1]:.1f}")

# Bollinger Bands
upper, mid, lower = utils.boll(close, period=20)
print(f"\nBollinger(20): upper={upper.iloc[-1]:.3f}, mid={mid.iloc[-1]:.3f}, lower={lower.iloc[-1]:.3f}")

# ATR
atr_val = utils.atr(high, low, close, period=14)
print(f"\nATR(14): {atr_val.iloc[-1]:.4f}")

# CCI
cci_val = utils.cci(high, low, close, period=14)
print(f"\nCCI(14): {cci_val.iloc[-1]:.2f}")

# Williams %R
wr_val = utils.wr(high, low, close, period=14)
print(f"\nWilliams %%R(14): {wr_val.iloc[-1]:.2f}")

# ROC
roc_val = utils.roc(close, period=12)
print(f"\nROC(12): {roc_val.iloc[-1]:.2f}%")

# ADX
pdi, mdi, adx, adxr = utils.adx(high, low, close, period=14)
print(f"\nADX(14): PDI={pdi.iloc[-1]:.2f}, MDI={mdi.iloc[-1]:.2f}, ADX={adx.iloc[-1]:.2f}, ADXR={adxr.iloc[-1]:.2f}")

# Cross detection
print(f"\nGolden Cross (MA5 vs MA20): {utils.golden_cross(ma5, utils.ma(close, 20)).iloc[-5:].tolist()}")


# ============================================================
# 2. Statistical Utilities
# ============================================================

print("\n" + "=" * 50)
print("2. Statistical Utilities")
print("=" * 50)

# Daily returns
daily_ret = close.pct_change().dropna()

# Z-Score
z = utils.zscore(close, window=20)
print(f"Z-Score(20) latest: {z.iloc[-1]:.3f}")

# Percentile Rank
pr = utils.percentile_rank(close, window=50)
print(f"50-day Percentile Rank: {pr.iloc[-1]:.1f}")

# Rolling Sharpe
sharpe = utils.rolling_sharpe(daily_ret, window=20, risk_free=0.03)
print(f"\nRolling Sharpe(20): {sharpe.iloc[-1]:.3f}")

# Drawdown
dd = utils.drawdown(close)
max_dd, dd_start, dd_end = utils.max_drawdown(close)
print(f"\nMax Drawdown: {max_dd * 100:.2f}%")
print(f"  From: {dd_start.date()} to {dd_end.date()}")

# Linear Regression (close vs its index)
x = pd.Series(range(len(close)), index=close.index, dtype=float)
reg = utils.linear_regression(x, close)
if reg:
    print(f"\nLinear Regression (price vs time):")
    print(f"  Alpha: {reg['alpha']:.4f}")
    print(f"  Beta:  {reg['beta']:.4f}")
    print(f"  R²:    {reg['r_squared']:.4f}")

# Compound return
total_ret = utils.compound_return(daily_ret)
print(f"\nCompound Return: {total_ret * 100:.2f}%")

# CAGR
cagr_val = utils.cagr(close.iloc[0], close.iloc[-1], 100 / 252)
print(f"CAGR (annualized): {cagr_val * 100:.2f}%")

# Log returns
log_ret = utils.log_return(close)
print(f"\nAvg Log Return: {log_ret.mean() * 100:.4f}%")

# Value at Risk
var_5 = utils.value_at_risk(daily_ret, confidence=0.05)
cvar_5 = utils.conditional_var(daily_ret, confidence=0.05)
print(f"\nVaR(5%):   {var_5 * 100:.2f}%")
print(f"CVaR(5%):  {cvar_5 * 100:.2f}%")

# Consecutive streaks
wins = utils.consecutive_wins(daily_ret)
losses = utils.consecutive_losses(daily_ret)
print(f"\nCurrent win streak: {wins.iloc[-1]}")
print(f"Max loss streak: {losses.max()}")

# Math utilities
print(f"\nFibonacci(10): {utils.fibonacci(10)}")
print(f"C(10,3) = {utils.comb(10, 3)}")
print(f"P(10,3) = {utils.perm(10, 3)}")


# ============================================================
# 3. Money Management
# ============================================================

print("\n" + "=" * 50)
print("3. Money Management & Position Sizing")
print("=" * 50)

capital = 100000

# Kelly Criterion
kelly = utils.kelly_criterion(win_rate=0.55, avg_win=1500, avg_loss=1000)
print(f"Kelly (WR=55%%, avg_win=1500, avg_loss=1000): {kelly * 100:.1f}% of capital")
print(f"Half-Kelly: {utils.half_kelly(0.55, 1500, 1000) * 100:.1f}%")

# Kelly from returns
sim_returns = pd.Series(np.random.choice([-0.02, 0.03], size=100, p=[0.45, 0.55]))
kelly_ret = utils.kelly_from_returns(sim_returns)
print(f"\nKelly from 100 simulated trades: {kelly_ret * 100:.1f}%")

# Fixed fractional sizing
shares = utils.fixed_fraction_size(
    capital=100000, risk_pct=0.02,
    entry_price=10.0, stop_price=9.5,
)
print(f"\nFixed Fractional (risk 2%%, entry=10.0, stop=9.5):")
print(f"  Buy {shares} shares (risk ¥{100000 * 0.02:,.0f})")

# Fixed ratio sizing
shares = utils.fixed_ratio_size(
    capital=100000, equity_ratio=0.10,
    entry_price=10.0,
)
print(f"\nFixed Ratio (allocate 10%%, price=10.0):")
print(f"  Buy {shares} shares (value ¥{shares * 10:,.0f})")

# ATR-based sizing
shares = utils.atr_position_size(
    capital=100000, risk_pct=0.02,
    atr=0.30, n_atr=2.0,
)
print(f"\nATR-based (risk 2%%, ATR=0.30, 2x ATR stop):")
print(f"  Buy {shares} shares")

# Volatility targeting
shares = utils.volatility_target_size(
    capital=100000, target_vol=0.15,
    price=10.0, vol_per_share=0.20,
)
print(f"\nVolatility Target (target vol=15%%, price=10.0, vol/share=0.20):")
print(f"  Buy {shares} shares")

# Portfolio weights
weights_eq = utils.equal_weight(5)
print(f"\nEqual Weight (5 assets): {[f'{w:.2f}' for w in weights_eq]}")

vols = [0.15, 0.25, 0.20, 0.30, 0.10]
weights_rp = utils.risk_parity_weights(vols)
print(f"Risk Parity (vols={vols}):")
print(f"  Weights: {[f'{w:.3f}' for w in weights_rp]}")

# Martingale / Anti-Martingale
print(f"\nMartingale (base=100, 3 losses, 2x): {utils.martingale_size(100, 3, 2.0)}")
print(f"Anti-Martingale (base=100, 3 wins, 1.5x): {utils.anti_martingale_size(100, 3, 1.5)}")
