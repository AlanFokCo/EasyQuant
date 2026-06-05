"""
08 - Utility Library Reference
==============================

Comprehensive tour of eqlib.utils: technical indicators,
statistical tools, and money management utilities. All demos
use real market data for practical context.

Teaching Objectives:
    - Technical indicators: ma, ema, macd, rsi, kdj, boll, atr, cci, adx
    - Statistics: zscore, percentile_rank, rolling_sharpe, drawdown, max_drawdown,
      linear_regression, value_at_risk, conditional_var
    - Money management: kelly_criterion, fixed_fraction_size, atr_position_size,
      volatility_target_size, risk_parity_weights

Expected Output:
    - Each utility function called with real data
    - Results printed with interpretation guidance

Run:
    python examples/08_utils_library.py
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from eqlib import get_price, utils
from examples._defaults import STOCKS


# ============================================================
# Data setup — fetch real market data for all demos
# ============================================================

security = STOCKS["liquor"]  # 600519 Kweichow Moutai
end = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")


# ============================================================
# 1. Technical Indicators
# ============================================================

def demo_indicators(close: pd.Series, high: pd.Series, low: pd.Series,
                    volume: pd.Series):
    """Demonstrate technical indicator utilities with real price data."""
    print(f"\n{'=' * 60}")
    print("1. Technical Indicators")
    print(f"{'=' * 60}")

    # --- Moving Averages ---
    ma5 = utils.ma(close, 5)
    ma20 = utils.ma(close, 20)
    ema10 = utils.ema(close, 10)
    print(f"  MA(5)  latest:  {ma5.iloc[-1]:>12.2f}  "
          f"{'price above MA5 → short-term bullish' if close.iloc[-1] > ma5.iloc[-1] else 'price below MA5 → short-term bearish'}")
    print(f"  MA(20) latest:  {ma20.iloc[-1]:>12.2f}  "
          f"{'price above MA20 → medium-term bullish' if close.iloc[-1] > ma20.iloc[-1] else 'price below MA20 → medium-term bearish'}")
    print(f"  EMA(10) latest: {ema10.iloc[-1]:>12.2f}  "
          f"(EMA reacts faster to recent prices than MA)")

    # --- MACD ---
    dif, dea, hist = utils.macd(close, fast=12, slow=26, signal=9)
    print(f"\n  MACD(12, 26, 9):")
    print(f"    DIF:  {dif.iloc[-1]:>+10.4f}")
    print(f"    DEA:  {dea.iloc[-1]:>+10.4f}")
    print(f"    Hist: {hist.iloc[-1]:>+10.4f}  "
          f"{'histogram positive → bullish momentum' if hist.iloc[-1] > 0 else 'histogram negative → bearish momentum'}")

    # --- RSI ---
    rsi14 = utils.rsi(close, 14)
    rsi_val = rsi14.iloc[-1]
    if rsi_val > 70:
        rsi_signal = "overbought (>70) — potential pullback"
    elif rsi_val < 30:
        rsi_signal = "oversold (<30) — potential bounce"
    else:
        rsi_signal = "neutral zone (30–70)"
    print(f"\n  RSI(14): {rsi_val:>8.1f}  {rsi_signal}")

    # --- KDJ ---
    k, d, j = utils.kdj(high, low, close, period=9)
    print(f"\n  KDJ(9):  K={k.iloc[-1]:>6.1f}  D={d.iloc[-1]:>6.1f}  J={j.iloc[-1]:>6.1f}")
    if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
        print(f"           K crossed above D → buy signal")
    elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
        print(f"           K crossed below D → sell signal")
    else:
        print(f"           No cross — trend continuation")

    # --- Bollinger Bands ---
    upper, mid, lower = utils.boll(close, period=20)
    price = close.iloc[-1]
    band_width = (upper.iloc[-1] - lower.iloc[-1]) / mid.iloc[-1] * 100
    print(f"\n  Bollinger Bands(20):")
    print(f"    Upper: {upper.iloc[-1]:>10.2f}")
    print(f"    Mid:   {mid.iloc[-1]:>10.2f}")
    print(f"    Lower: {lower.iloc[-1]:>10.2f}")
    print(f"    Width: {band_width:>8.1f}%  "
          f"{'wide bands → high volatility' if band_width > 10 else 'narrow bands → low volatility / squeeze'}")

    # --- ATR ---
    atr_val = utils.atr(high, low, close, period=14)
    atr_pct = atr_val.iloc[-1] / price * 100
    print(f"\n  ATR(14): {atr_val.iloc[-1]:>8.2f}  "
          f"({atr_pct:.1f}% of price — "
          f"{'high' if atr_pct > 3 else 'moderate' if atr_pct > 1.5 else 'low'} daily range)")

    # --- CCI ---
    cci_val = utils.cci(high, low, close, period=14)
    cci_latest = cci_val.iloc[-1]
    if cci_latest > 100:
        cci_signal = "overbought (>100)"
    elif cci_latest < -100:
        cci_signal = "oversold (<-100)"
    else:
        cci_signal = "neutral (-100 to +100)"
    print(f"\n  CCI(14): {cci_latest:>+10.2f}  {cci_signal}")

    # --- ADX ---
    pdi, mdi, adx_v, adxr = utils.adx(high, low, close, period=14)
    adx_latest = adx_v.iloc[-1]
    if adx_latest > 25:
        trend = "strong trend"
    elif adx_latest > 15:
        trend = "moderate trend"
    else:
        trend = "weak / no trend (range-bound)"
    print(f"\n  ADX(14): PDI={pdi.iloc[-1]:>6.2f}  MDI={mdi.iloc[-1]:>6.2f}  "
          f"ADX={adx_latest:>6.2f}  ADXR={adxr.iloc[-1]:>6.2f}")
    print(f"           {trend}"
          f"{'  (bullish — PDI > MDI)' if pdi.iloc[-1] > mdi.iloc[-1] else '  (bearish — MDI > PDI)'}")

    # --- Golden Cross Detection ---
    ma5_series = utils.ma(close, 5)
    ma20_series = utils.ma(close, 20)
    crosses = utils.golden_cross(ma5_series, ma20_series)
    recent_crosses = crosses.tail(20)
    n_crosses = recent_crosses.sum()
    print(f"\n  Golden Cross (MA5 vs MA20): "
          f"{n_crosses} occurrence(s) in last 20 bars  "
          f"{'→ bullish signal active' if crosses.iloc[-1] else ''}")


# ============================================================
# 2. Statistical Utilities
# ============================================================

def demo_statistics(close: pd.Series):
    """Demonstrate statistical utility functions with real price data."""
    print(f"\n{'=' * 60}")
    print("2. Statistical Utilities")
    print(f"{'=' * 60}")

    daily_ret = close.pct_change().dropna()

    # --- Z-Score ---
    z = utils.zscore(close, window=20)
    z_latest = z.iloc[-1]
    if abs(z_latest) > 2:
        z_signal = "extreme deviation (>2σ) — mean-reversion candidate"
    elif abs(z_latest) > 1:
        z_signal = "moderate deviation (1–2σ)"
    else:
        z_signal = "within 1σ — near recent mean"
    print(f"  Z-Score(20):  {z_latest:>+8.3f}  {z_signal}")

    # --- Percentile Rank ---
    pr = utils.percentile_rank(close, window=50)
    pr_latest = pr.iloc[-1]
    print(f"  Percentile Rank(50): {pr_latest:>6.1f}%  "
          f"{'near 50-day high' if pr_latest > 80 else 'near 50-day low' if pr_latest < 20 else 'mid-range'}")

    # --- Rolling Sharpe ---
    sharpe = utils.rolling_sharpe(daily_ret, window=20, risk_free=0.03)
    sharpe_latest = sharpe.iloc[-1]
    print(f"\n  Rolling Sharpe(20):  {sharpe_latest:>+8.3f}  "
          f"{'strong risk-adjusted return' if sharpe_latest > 1.5 else 'moderate' if sharpe_latest > 0 else 'negative excess return'}")

    # --- Drawdown ---
    dd = utils.drawdown(close)
    print(f"  Current Drawdown:    {dd.iloc[-1]:>+8.2%}  "
          f"(0% = at peak)")

    # --- Max Drawdown ---
    max_dd, dd_start, dd_end = utils.max_drawdown(close)
    print(f"  Max Drawdown:        {max_dd:>+8.2%}")
    print(f"    Period: {dd_start.date()} → {dd_end.date()}")

    # --- Linear Regression (price vs time) ---
    x = pd.Series(range(len(close)), index=close.index, dtype=float)
    reg = utils.linear_regression(x, close)
    if reg:
        trend_dir = "upward" if reg["beta"] > 0 else "downward"
        print(f"\n  Linear Regression (price vs time):")
        print(f"    Slope (β):  {reg['beta']:>+10.4f}  ({trend_dir} trend)")
        print(f"    Intercept:  {reg['alpha']:>10.4f}")
        print(f"    R²:         {reg['r_squared']:>10.4f}  "
              f"{'strong fit' if reg['r_squared'] > 0.7 else 'weak fit — noisy price action'}")
        print(f"    t-stat:     {reg['t_stat']:>10.2f}  "
              f"{'statistically significant' if abs(reg['t_stat']) > 2 else 'not significant'}")

    # --- Value at Risk ---
    var_5 = utils.value_at_risk(daily_ret, confidence=0.05)
    cvar_5 = utils.conditional_var(daily_ret, confidence=0.05)
    print(f"\n  VaR(5%):   {var_5:>8.2%}  "
          f"(worst 5% daily loss threshold)")
    print(f"  CVaR(5%):  {cvar_5:>8.2%}  "
          f"(average loss beyond VaR — tail risk)")
    print(f"  CVaR/VaR:  {cvar_5 / var_5 if var_5 != 0 else 0:>8.2f}x  "
          f"({'fat tails' if cvar_5 / var_5 > 1.3 else 'thin tails'} if > 1.3)")

    # --- Log Returns ---
    log_ret = utils.log_return(close)
    avg_log = log_ret.mean()
    print(f"\n  Avg Log Return:  {avg_log * 100:>+8.4f}%  "
          f"(continuously compounded daily return)")


# ============================================================
# 3. Money Management
# ============================================================

def demo_money_management():
    """Demonstrate money management and position sizing utilities."""
    print(f"\n{'=' * 60}")
    print("3. Money Management & Position Sizing")
    print(f"{'=' * 60}")

    capital = 100_000

    # --- Kelly Criterion ---
    win_rate = 0.55
    avg_win = 1500
    avg_loss = 1000
    kelly = utils.kelly_criterion(win_rate, avg_win, avg_loss)
    half_k = utils.half_kelly(win_rate, avg_win, avg_loss)
    print(f"  Kelly Criterion (WR={win_rate:.0%}, avg_win={avg_win}, avg_loss={avg_loss}):")
    print(f"    Full Kelly:  {kelly * 100:>6.1f}% of capital  "
          f"(theoretical optimal — aggressive)")
    print(f"    Half Kelly:  {half_k * 100:>6.1f}% of capital  "
          f"(conservative — recommended for live trading)")

    # --- Fixed Fractional Sizing ---
    entry_price = 50.0
    stop_price = 47.5
    risk_pct = 0.02
    shares = utils.fixed_fraction_size(
        capital=capital, risk_pct=risk_pct,
        entry_price=entry_price, stop_price=stop_price,
    )
    risk_amount = capital * risk_pct
    print(f"\n  Fixed Fractional (risk {risk_pct:.0%} of capital):")
    print(f"    Entry: {entry_price:.2f}, Stop: {stop_price:.2f}, "
          f"Risk: ¥{risk_amount:,.0f}")
    print(f"    Position: {shares} shares "
          f"(¥{shares * entry_price:,.0f} = {shares * entry_price / capital:.1%} of capital)")

    # --- ATR-based Sizing ---
    atr_val = 1.50
    n_atr = 2.0
    shares_atr = utils.atr_position_size(
        capital=capital, risk_pct=risk_pct,
        atr=atr_val, n_atr=n_atr,
    )
    print(f"\n  ATR-based Sizing (risk {risk_pct:.0%}, ATR={atr_val:.2f}, "
          f"stop={n_atr:.0f}×ATR):")
    print(f"    Stop distance: {atr_val * n_atr:.2f} per share")
    print(f"    Position: {shares_atr} shares "
          f"(¥{shares_atr * entry_price:,.0f} at price {entry_price:.2f})")

    # --- Volatility Targeting ---
    target_vol = 0.15
    vol_per_share = 0.75
    price = 50.0
    shares_vol = utils.volatility_target_size(
        capital=capital, target_vol=target_vol,
        price=price, vol_per_share=vol_per_share,
    )
    print(f"\n  Volatility Target (target vol={target_vol:.0%}):")
    print(f"    Price: {price:.2f}, Vol/share: {vol_per_share:.2f}")
    print(f"    Position: {shares_vol} shares "
          f"(¥{shares_vol * price:,.0f} = {shares_vol * price / capital:.1%} of capital)")

    # --- Equal Weight ---
    n_assets = 5
    weights_eq = utils.equal_weight(n_assets)
    print(f"\n  Equal Weight ({n_assets} assets):")
    print(f"    Weights: {[f'{w:.2f}' for w in weights_eq]}  "
          f"(each asset gets {weights_eq[0]:.0%})")

    # --- Risk Parity Weights ---
    vols = [0.15, 0.25, 0.20, 0.30, 0.10]
    weights_rp = utils.risk_parity_weights(vols)
    print(f"\n  Risk Parity Weights:")
    print(f"    Asset vols:      {vols}")
    print(f"    Weights:         {[f'{w:.3f}' for w in weights_rp]}")
    print(f"    Interpretation:  low-vol assets get higher weight so each "
          f"contributes equally to portfolio risk")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("08 - Utility Library Reference")
    print("=" * 60)
    print(f"  Security: {security} (Kweichow Moutai)")
    print(f"  Period:   {start} → {end}")

    df = get_price(security, start_date=start, end_date=end)
    if df is None or df.empty:
        print(f"Error: no data for {security}. Check network connection.")
        raise SystemExit(1)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    print(f"  Bars fetched: {len(df)}")

    demo_indicators(close, high, low, volume)
    demo_statistics(close)
    demo_money_management()

    print(f"\n{'=' * 60}")
    print("Done. All utility functions demonstrated with real data.")
    print(f"{'=' * 60}")
