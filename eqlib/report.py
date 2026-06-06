"""Report generation: chart (PNG), HTML (TradingView lightweight-charts), JSON, and Markdown."""

import os
import json
import html
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["font.sans-serif"] = ["PingFang HK", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

from eqlib.data import fetch_stock_data, get_price
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
from eqlib.brand import (
    BRAND_NAME,
    apply_matplotlib_brand,
    html_footer_brand_chip,
    html_header_brand_lockup,
)
import pandas as pd
import numpy as np


def _to_tv_date(date_val):
    """Convert date/datetime to lightweight-charts time string (YYYY-MM-DD).

    Handles datetime.datetime, datetime.date, pd.Timestamp, numpy datetime64,
    and arbitrary objects via ``str(...)[:10]`` fallback.
    """
    # pd.Timestamp is a subclass of datetime.datetime, which is a subclass
    # of datetime.date — so checking against datetime.date covers all three.
    if isinstance(date_val, datetime.date):
        return date_val.strftime("%Y-%m-%d")
    try:
        ts = pd.Timestamp(date_val)
        if not pd.isna(ts):
            return ts.strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(date_val)[:10]


def _compute_support_resistance(closes, highs, lows, window=20):
    """Compute dynamic support and resistance using rolling min/max of highs/lows."""
    support = lows.rolling(window, min_periods=5).min()
    resistance = highs.rolling(window, min_periods=5).max()
    return support, resistance


def _compute_pivot_points(df, window=20):
    """Compute pivot point levels using rolling averages."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    rolling_typical = typical.rolling(window, min_periods=5).mean()
    rolling_range = (df["high"].rolling(window, min_periods=5).max() -
                     df["low"].rolling(window, min_periods=5).min())
    r1 = rolling_typical + rolling_range / 2
    s1 = rolling_typical - rolling_range / 2
    r2 = rolling_typical + rolling_range
    s2 = rolling_typical - rolling_range
    return r1, s1, r2, s2


def _build_return_series(recorded, initial):
    """Build cumulative return (%) series from recorded values."""
    returns = []
    if not recorded:
        return returns

    # Support both dict (date -> entry) and list
    if isinstance(recorded, dict):
        entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min))
    else:
        entries = recorded

    by_date = {}
    for r in entries:
        if "total_value" in r:
            d = _to_tv_date(r["date"])
            by_date[d] = r["total_value"]

    if not by_date:
        return returns

    sorted_dates = sorted(by_date.keys())
    init_val = by_date[sorted_dates[0]]
    if init_val <= 0:
        init_val = initial
    if init_val <= 0:
        return returns

    for d in sorted_dates:
        val = by_date[d]
        cum_ret = round((val - init_val) / init_val * 100, 3)
        returns.append({"time": d, "value": cum_ret})

    return returns


def _build_daily_pnl(recorded, initial):
    """Build daily P&L and daily return % series."""
    pnl_bars = []
    ret_bars = []
    if not recorded:
        return pnl_bars, ret_bars

    by_date = {}
    entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min)) if isinstance(recorded, dict) else recorded
    for r in entries:
        if "total_value" in r:
            d = _to_tv_date(r["date"])
            by_date[d] = r["total_value"]

    if not by_date:
        return pnl_bars, ret_bars

    sorted_dates = sorted(by_date.keys())
    prev_val = None
    for d in sorted_dates:
        val = by_date[d]
        if prev_val is not None:
            daily_pnl = val - prev_val
            daily_ret = round((val - prev_val) / prev_val * 100, 3)
            pnl_bars.append({
                "time": d, "value": round(daily_pnl, 2),
                "color": "#52c41a" if daily_pnl >= 0 else "#f5222d",
            })
            ret_bars.append({
                "time": d, "value": daily_ret,
                "color": "#52c41a" if daily_ret >= 0 else "#f5222d",
            })
        else:
            pnl_bars.append({"time": d, "value": 0, "color": "#484f58"})
            ret_bars.append({"time": d, "value": 0, "color": "#484f58"})
        prev_val = val

    return pnl_bars, ret_bars


def _build_drawdown_from_cumulative_pct(cum_points):
    """From cumulative total return % series [{time, value}, ...], build drawdown % from running peak.

    Same definition as strategy drawdown: current cumulative % minus max cumulative % seen so far.
    """
    if not cum_points:
        return []
    out = []
    peak = cum_points[0]["value"]
    for d in cum_points:
        v = d["value"]
        if v > peak:
            peak = v
        out.append({"time": d["time"], "value": round(v - peak, 3)})
    return out


def _align_index_close_to_times(target_time_strings: list, price_df: pd.DataFrame) -> list:
    """Build cumulative index return (%) series aligned to strategy chart ``time`` keys.

    Uses the last available index close on or before each target date (forward-filled
    after union reindex), then expresses returns vs the close on the **first** target
    date. This avoids empty series when the first portfolio bar has no exact index row
    in the sliced frame (calendar edge / timezone) or when the slice starts on a
    non-trading day.
    """
    if not target_time_strings or price_df is None or price_df.empty:
        return []
    if "close" not in price_df.columns:
        return []
    s = price_df["close"].astype(float).copy()
    # Ensure index is a proper DatetimeIndex (handles date objects, strings, etc.)
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s.dropna()  # Drop rows where date conversion failed
    if s.empty:
        return []
    s = s[~s.index.duplicated(keep="last")]
    try:
        target_ix = pd.DatetimeIndex([pd.Timestamp(t) for t in target_time_strings])
    except Exception:
        return []
    if target_ix.empty:
        return []
    try:
        union_ix = s.index.union(target_ix)
    except Exception:
        # Fallback: forward-fill to each target date individually
        return _align_fallback(s, target_ix, target_time_strings)
    s_ff = s.reindex(union_ix).sort_index().ffill()
    at_targets = s_ff.reindex(target_ix)
    if at_targets.isna().any():
        at_targets = at_targets.bfill().ffill()
    if at_targets.isna().all():
        return []
    base = float(at_targets.iloc[0])
    if base <= 0 or np.isnan(base):
        return []
    out = []
    for i, t in enumerate(target_time_strings):
        pr = float(at_targets.iloc[i])
        if np.isnan(pr):
            continue
        out.append({"time": t, "value": round((pr / base - 1.0) * 100.0, 3)})
    return out


def _align_fallback(s: pd.Series, target_ix: pd.DatetimeIndex, target_time_strings: list) -> list:
    """Fallback alignment when union fails: for each target date, find the last available price."""
    s = s.sort_index()
    out = []
    base = None
    for i, ts in enumerate(target_ix):
        mask = s.index <= ts
        available = s[mask]
        if available.empty:
            continue
        pr = float(available.iloc[-1])
        if np.isnan(pr):
            continue
        if base is None:
            base = pr
        if base <= 0:
            continue
        out.append({"time": target_time_strings[i], "value": round((pr / base - 1.0) * 100.0, 3)})
    return out


def attach_chart_dual_indices(result: dict) -> None:
    """Fetch CSI300 + SSE index closes during backtest and attach aligned cumulative % series.

    Populates ``result['chart_index_hs300']`` and ``result['chart_index_sse']`` as
    lists of ``{{"time": "YYYY-MM-DD", "value": float}}`` matching portfolio record
    dates (same length/order as strategy cumulative return chart). Used by
    ``generate_html_report`` so charts render without a second fragile fetch.

    Safe no-op if ``context`` / ``recorded_values`` missing or fetch fails.
    """
    ctx = result.get("context")
    if ctx is None:
        return
    recorded = result.get("recorded_values")
    if not recorded:
        result["chart_index_hs300"] = []
        result["chart_index_sse"] = []
        return
    initial = getattr(ctx.portfolio, "starting_cash", 0) or 0
    cum_pts = _build_return_series(recorded, initial)
    if not cum_pts:
        result["chart_index_hs300"] = []
        result["chart_index_sse"] = []
        return
    target_times = [p["time"] for p in cum_pts]
    first_d = datetime.datetime.strptime(target_times[0], "%Y-%m-%d").date()
    last_d = datetime.datetime.strptime(target_times[-1], "%Y-%m-%d").date()
    pad = datetime.timedelta(days=400)
    ctx_start = getattr(ctx, "start_date", first_d)
    ctx_end = getattr(ctx, "end_date", last_d)
    fetch_start = min(first_d, ctx_start) - pad
    fetch_end = max(last_d, ctx_end)
    try:
        hs_df = fetch_stock_data("000300.XSHG", fetch_start, fetch_end)
        sse_df = fetch_stock_data("000001.XSHG", fetch_start, fetch_end)
    except Exception as exc:
        from eqlib.logger import log
        log.warn("attach_chart_dual_indices: index fetch failed: %s", exc)
        result["chart_index_hs300"] = []
        result["chart_index_sse"] = []
        return
    hs_line = _align_index_close_to_times(target_times, hs_df)
    sse_line = _align_index_close_to_times(target_times, sse_df)
    has_raw = (hs_df is not None and not hs_df.empty) or (sse_df is not None and not sse_df.empty)
    if (not hs_line or not sse_line) and has_raw:
        from eqlib.logger import log
        log.warn(
            "attach_chart_dual_indices: aligned series empty "
            "(hs_pts=%s, sse_pts=%s, hs_rows=%s, sse_rows=%s, strategy_pts=%s)",
            len(hs_line), len(sse_line),
            len(hs_df) if hs_df is not None else 0,
            len(sse_df) if sse_df is not None else 0,
            len(target_times),
        )
    result["chart_index_hs300"] = hs_line
    result["chart_index_sse"] = sse_line


def _fetch_index_returns(index_symbol, start, end, recorded):
    """Fetch index data and compute cumulative return (%) series."""
    result_data = []
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol=index_symbol)
        if df.empty:
            return result_data
        df["date"] = pd.to_datetime(df["date"]).dt.date
        start_d = start if isinstance(start, datetime.date) else datetime.date(2000, 1, 1)
        end_d = end if isinstance(end, datetime.date) else datetime.date(2100, 12, 31)
        df = df[(df["date"] >= start_d) & (df["date"] <= end_d)].sort_values("date")
        if df.empty or len(df) < 2:
            return result_data
        init_price = df["close"].iloc[0]
        if init_price <= 0:
            return result_data
        entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min)) if isinstance(recorded, dict) else recorded
        for r in entries:
            rd = r["date"]
            if isinstance(rd, str):
                rd = datetime.datetime.strptime(rd, "%Y-%m-%d").date()
            mask = df["date"] <= rd
            if mask.any():
                price = df.loc[mask, "close"].iloc[-1]
                cum_ret = round((price - init_price) / init_price * 100, 3)
                result_data.append({"time": _to_tv_date(r["date"]), "value": cum_ret})
    except Exception:
        pass
    return result_data


def _fetch_benchmark_returns(benchmark_code, start, end, recorded):
    """Fetch the actual benchmark's cumulative return series for the TradingView chart.

    Converts a benchmark code like '000300.XSHG' to the akshare format
    ('sh000300') and delegates to _fetch_index_returns().
    """
    code = benchmark_code.replace(".XSHG", "").replace(".XSHE", "")
    # Shanghai: codes starting with 6/9/000; Shenzhen: everything else
    if code.startswith(("6", "9")) or code.startswith("000"):
        ak_symbol = "sh" + code
    else:
        ak_symbol = "sz" + code
    return _fetch_index_returns(ak_symbol, start, end, recorded)


def generate_chart(result, out_path):
    """Generate professional backtest chart (dark theme, 4-panel):
    - Top-left: strategy cumulative return (%) vs benchmark (%) with trade markers
    - Top-right: dimension score bars (6-dimension grade)
    - Middle: portfolio drawdown (%)
    - Bottom: monthly returns strip (last 12 months)
    """
    from eqlib.attribution import analyze_returns, grade_strategy
    from eqlib.brand import DARK_COLORS, apply_matplotlib_dark_theme, apply_matplotlib_brand

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)
    c = DARK_COLORS

    pf_entries = sorted(
        recorded.values(), key=lambda x: x.get("date", datetime.date.min)
    ) if isinstance(recorded, dict) else recorded
    pf_records = [r for r in pf_entries if "total_value" in r]
    if not pf_records:
        plt.close()
        return

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    pf_dates = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in pf_records])
    pf_values = pd.Series([r["total_value"] for r in pf_records], index=pf_dates)
    strat_cum_ret = (pf_values / initial - 1) * 100

    # Benchmark
    bench_cum_ret = None
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_df = bench_df.sort_index()
            bench_init = bench_df["close"].iloc[0]
            bench_cum_ret = pd.Series(
                (bench_df["close"] / bench_init - 1) * 100,
                index=bench_df.index,
            )
    except Exception:
        pass

    # Figure: 3 rows, 2 columns (top-right for score bars)
    fig = plt.figure(figsize=(14, 9), facecolor=c["bg_primary"])
    gs = fig.add_gridspec(3, 2, height_ratios=[3, 1.5, 0.6],
                          hspace=0.15, wspace=0.12,
                          left=0.06, right=0.96, top=0.88, bottom=0.04)
    ax = fig.add_subplot(gs[0, 0])          # cumulative return
    ax_radar = fig.add_subplot(gs[0, 1])    # dimension score bars
    ax_dd = fig.add_subplot(gs[1, :])       # drawdown (full width)
    ax_monthly = fig.add_subplot(gs[2, :])  # monthly strip (full width)

    # --- Cumulative return ---
    ax.set_facecolor(c["bg_card"])
    ax.plot(pf_dates.to_numpy(), strat_cum_ret.values,
            color=c["chart_strategy"], linewidth=1.8, label="Strategy", zorder=5)
    if bench_cum_ret is not None:
        bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")
        ax.plot(bench_cum_ret.index.to_numpy(), bench_cum_ret.values,
                color=c["chart_hs300"], linewidth=1.2, alpha=0.7, label=bench_label, zorder=4)
    ax.axhline(0, color=c["text_dim"], linewidth=0.6, linestyle="--")

    # Buy/sell trade markers
    buys = [t for t in trade_log if t["type"] == "BUY"]
    sells = [t for t in trade_log if t["type"] == "SELL"]
    if len(buys) <= 50:
        for b in buys:
            idx = pf_values.index.get_indexer([pd.Timestamp(b["date"])], method="nearest")[0]
            ret_at_buy = (pf_values.iloc[idx] / initial - 1) * 100
            ax.plot(b["date"], ret_at_buy, marker="^", color=c["up"],
                    markersize=5, zorder=3)
    if len(sells) <= 50:
        for s in sells:
            idx = pf_values.index.get_indexer([pd.Timestamp(s["date"])], method="nearest")[0]
            ret_at_sell = (pf_values.iloc[idx] / initial - 1) * 100
            ax.plot(s["date"], ret_at_sell, marker="v", color=c["down"],
                    markersize=5, zorder=3)

    ax.legend(loc="upper left", fontsize=8, facecolor=c["bg_elevated"],
              edgecolor=c["border"], labelcolor=c["text_secondary"])
    ax.set_ylabel("Cumulative Return (%)", fontsize=9, color=c["text_secondary"])
    ax.tick_params(colors=c["text_secondary"], labelsize=7)
    ax.grid(True, alpha=0.15, color=c["border_light"])
    for spine in ax.spines.values():
        spine.set_color(c["border"])
    ax.set_title(
        f"PnL: {pnl:+,.0f} ({pnl_pct:+.2f}%)  |  Trades: {len(trade_log)}",
        fontsize=11, fontweight="bold", color=c["text_primary"],
    )

    # Metrics annotation
    if analytics:
        ann_ret = analytics.get("annual_return", 0)
        sharpe = analytics.get("sharpe_ratio", 0)
        max_dd = analytics.get("max_drawdown", 0)
        ax.text(
            0.98, 0.03,
            f"Ann.Ret {ann_ret:+.1%}  Sharpe {sharpe:.2f}  MaxDD {max_dd:.1%}",
            transform=ax.transAxes, fontsize=8, fontfamily="monospace",
            ha="right", va="bottom", color=c["text_secondary"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor=c["bg_elevated"],
                      edgecolor=c["border"], alpha=0.9),
        )

    # --- Dimension score bars ---
    ax_radar.set_facecolor(c["bg_card"])
    dims = grade_info.get("dimensions", [])
    if dims:
        dim_scores = [d["score"] for d in dims]
        short_names = ["Return", "Risk", "Adj.", "Trade", "Excess", "Stab."]
        bars = ax_radar.barh(short_names[:len(dims)], dim_scores,
                             color=c["accent"], alpha=0.7, height=0.6)
        ax_radar.set_xlim(0, 100)
        ax_radar.tick_params(colors=c["text_secondary"], labelsize=7)
        ax_radar.set_title(f"Grade: {grade_info['overall']} ({grade_info['score']:.0f}/100)",
                          fontsize=10, color=c["text_primary"])
        for spine in ax_radar.spines.values():
            spine.set_color(c["border"])
        ax_radar.grid(True, axis="x", alpha=0.15, color=c["border_light"])

    # --- Drawdown ---
    ax_dd.set_facecolor(c["bg_card"])
    rolling_max = pf_values.cummax()
    dd_pct = (pf_values - rolling_max) / rolling_max * 100
    ax_dd.fill_between(dd_pct.index.to_numpy(), dd_pct.values, 0,
                       color=c["down"], alpha=0.4, zorder=2)
    ax_dd.axhline(0, color=c["text_dim"], linewidth=0.6, linestyle="--")
    ax_dd.set_ylabel("Drawdown (%)", fontsize=9, color=c["text_secondary"])
    ax_dd.tick_params(colors=c["text_secondary"], labelsize=7)
    ax_dd.grid(True, alpha=0.15, color=c["border_light"])
    for spine in ax_dd.spines.values():
        spine.set_color(c["border"])
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    n_months = max(1, len(pf_dates) // 30)
    ax_dd.xaxis.set_major_locator(mdates.MonthLocator(interval=n_months))

    # --- Monthly returns strip ---
    ax_monthly.set_facecolor(c["bg_card"])
    ax_monthly.axis("off")
    if analytics and analytics.get("monthly_returns"):
        mr = analytics["monthly_returns"]
        month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
        x_positions = np.linspace(0.02, 0.98, 12)
        # Show last 12 months to handle multi-year backtests
        sorted_keys = sorted(mr.keys())
        display_keys = sorted_keys[-12:] if len(sorted_keys) > 12 else sorted_keys
        for key in display_keys:
            val = mr[key]
            month_idx = int(key.split("-")[1]) - 1
            color = c["up"] if val >= 0 else c["down"]
            alpha_val = min(1.0, abs(val) * 10)
            ax_monthly.text(x_positions[month_idx], 0.5,
                           f"{month_labels[month_idx]}\n{val:+.1%}",
                           ha="center", va="center", fontsize=7,
                           color=color, fontweight="600",
                           bbox=dict(boxstyle="round,pad=0.3",
                                    facecolor=color, alpha=alpha_val * 0.15,
                                    edgecolor="none"))

    apply_matplotlib_brand(fig, text_color=c["text_primary"])
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.2,
                facecolor=c["bg_primary"])
    plt.close()
    print(f"Chart saved: {out_path}")


def _compute_symbol_kline(symbol, start, end, ohlcv_data, trade_log):
    """Compute K-line and technical indicator data for a single symbol.

    Returns a dict with: candlestick_data, volume_data, ma5/20/60_data,
    support_data, resistance_data, rsi_data, macd_data, macd_signal_data,
    macd_hist_data, bb_upper/middle/lower_data, markers, tech_stats.
    """
    candlestick_data, ma5_data, ma20_data, ma60_data = [], [], [], []
    volume_data, support_data, resistance_data = [], [], []

    df = ohlcv_data.get(symbol, pd.DataFrame())
    if df.empty:
        try:
            from eqlib.data import fetch_stock_data
            df = fetch_stock_data(symbol, start, end)
        except Exception:
            pass

    if not df.empty:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        df_sorted = df.sort_index().loc[start_ts:end_ts]
        if df_sorted.empty:
            df_sorted = df.sort_index()
        closes, highs, lows = df_sorted["close"], df_sorted["high"], df_sorted["low"]
        ma5, ma20, ma60 = closes.rolling(5).mean(), closes.rolling(20).mean(), closes.rolling(60).mean()
        support, resistance = _compute_support_resistance(closes, highs, lows, window=20)

        for (date, row), m5, m20, m60, sup, res in zip(
                df_sorted.iterrows(), ma5, ma20, ma60, support, resistance):
            d = _to_tv_date(date)
            o, h, l, c, v = float(row.get("open", 0)), float(row.get("high", 0)), float(row.get("low", 0)), float(row.get("close", 0)), float(row.get("volume", 0))
            candlestick_data.append({"time": d, "open": round(o, 3), "high": round(h, 3), "low": round(l, 3), "close": round(c, 3)})
            volume_data.append({"time": d, "value": round(v, 0), "color": "#26a69a" if c >= o else "#ef5350"})
            if not pd.isna(m5): ma5_data.append({"time": d, "value": round(float(m5), 3)})
            if not pd.isna(m20): ma20_data.append({"time": d, "value": round(float(m20), 3)})
            if not pd.isna(m60): ma60_data.append({"time": d, "value": round(float(m60), 3)})
            if not pd.isna(sup): support_data.append({"time": d, "value": round(float(sup), 3)})
            if not pd.isna(res): resistance_data.append({"time": d, "value": round(float(res), 3)})
    else:
        df_sorted = pd.DataFrame()

    # RSI(14), MACD(12,26,9), Bollinger Bands(20,2)
    rsi_data, macd_data, macd_signal_data, macd_hist_data = [], [], [], []
    bb_upper_data, bb_middle_data, bb_lower_data = [], [], []

    if not df.empty and not df_sorted.empty and len(df_sorted) >= 26:
        closes = df_sorted["close"]
        delta = closes.diff()
        gain, loss = delta.clip(lower=0), (-delta.clip(upper=0))
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))

        ema_fast = closes.ewm(span=12, adjust=False).mean()
        ema_slow = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        bb_middle_series = closes.rolling(20).mean()
        bb_std = closes.rolling(20).std()
        bb_upper_series, bb_lower_series = bb_middle_series + 2 * bb_std, bb_middle_series - 2 * bb_std

        for (date, row), rsi_v, macd_v, sig_v, hist_v, bb_u, bb_m, bb_l in zip(
                df_sorted.iterrows(), rsi_series, macd_line, signal_line,
                histogram, bb_upper_series, bb_middle_series, bb_lower_series):
            d = _to_tv_date(date)
            if not pd.isna(rsi_v): rsi_data.append({"time": d, "value": round(float(rsi_v), 3)})
            if not pd.isna(macd_v): macd_data.append({"time": d, "value": round(float(macd_v), 4)})
            if not pd.isna(sig_v): macd_signal_data.append({"time": d, "value": round(float(sig_v), 4)})
            if not pd.isna(hist_v):
                hv = round(float(hist_v), 4)
                macd_hist_data.append({"time": d, "value": hv, "color": "rgba(245,34,45,0.6)" if hv >= 0 else "rgba(82,196,26,0.6)"})
            if not pd.isna(bb_u): bb_upper_data.append({"time": d, "value": round(float(bb_u), 3)})
            if not pd.isna(bb_m): bb_middle_data.append({"time": d, "value": round(float(bb_m), 3)})
            if not pd.isna(bb_l): bb_lower_data.append({"time": d, "value": round(float(bb_l), 3)})

    # Buy/sell markers for this symbol only
    markers = []
    for t in trade_log:
        if t["security"] == symbol:
            markers.append({
                "time": _to_tv_date(t["date"]),
                "position": "belowBar" if t["type"] == "BUY" else "aboveBar",
                "color": "#26a69a" if t["type"] == "BUY" else "#ef5350",
                "shape": "arrowUp" if t["type"] == "BUY" else "arrowDown",
                "text": f"{'买' if t['type'] == 'BUY' else '卖'} {t['amount']}",
            })
    markers.sort(key=lambda x: x["time"])

    # Technical summary stats
    tech_stats = {}
    if not df.empty:
        df_s = df.sort_index()
        c = float(df_s["close"].iloc[-1])
        ma5_last = float(df_s["close"].rolling(5).mean().iloc[-1])
        ma20_last = float(df_s["close"].rolling(20).mean().iloc[-1])
        ma60_ser = df_s["close"].rolling(60).mean().dropna()
        ma60_v = round(float(ma60_ser.iloc[-1]), 3) if len(ma60_ser) > 0 else None
        atr14 = _compute_atr(df_s["high"], df_s["low"], df_s["close"], 14)
        vol20 = df_s["volume"].rolling(20).mean().iloc[-1]
        vol_ratio = round(float(df_s["volume"].iloc[-1] / vol20), 2) if vol20 > 0 else None

        rsi_last = rsi_data[-1]["value"] if rsi_data else None
        macd_last = macd_data[-1]["value"] if macd_data else None
        macd_sig_last = macd_signal_data[-1]["value"] if macd_signal_data else None
        macd_hist_last = macd_hist_data[-1]["value"] if macd_hist_data else None
        bb_u_last = bb_upper_data[-1]["value"] if bb_upper_data else None
        bb_m_last = bb_middle_data[-1]["value"] if bb_middle_data else None
        bb_l_last = bb_lower_data[-1]["value"] if bb_lower_data else None
        bb_width = round((bb_u_last - bb_l_last) / bb_m_last * 100, 3) if bb_u_last is not None and bb_m_last and bb_m_last != 0 else None

        tech_stats = {
            "latest_price": round(c, 3),
            "ma5": round(ma5_last, 3),
            "ma20": round(ma20_last, 3),
            "ma60": ma60_v,
            "atr14": round(float(atr14), 3) if atr14 else None,
            "vol_ratio": vol_ratio,
            "period_high": round(float(df_s["high"].max()), 3),
            "period_low": round(float(df_s["low"].min()), 3),
            "rsi14": rsi_last,
            "macd": macd_last,
            "macd_signal": macd_sig_last,
            "macd_hist": macd_hist_last,
            "bb_upper": bb_u_last,
            "bb_middle": bb_m_last,
            "bb_lower": bb_l_last,
            "bb_width": bb_width,
        }

    return {
        "candlestick_data": candlestick_data,
        "volume_data": volume_data,
        "ma5_data": ma5_data, "ma20_data": ma20_data, "ma60_data": ma60_data,
        "support_data": support_data, "resistance_data": resistance_data,
        "rsi_data": rsi_data, "macd_data": macd_data,
        "macd_signal_data": macd_signal_data, "macd_hist_data": macd_hist_data,
        "bb_upper_data": bb_upper_data, "bb_middle_data": bb_middle_data,
        "bb_lower_data": bb_lower_data,
        "markers": markers,
        "tech_stats": tech_stats,
    }


def _compute_chart_data(result):
    """Compute all chart data arrays from a backtest result dict.

    Returns a dict with: candlestick_data, volume_data, ma5/20/60_data,
    support_data, resistance_data, rsi_data, macd_data, macd_signal_data,
    macd_hist_data, bb_upper/middle/lower_data, markers, cum_return_data,
    ret_hs300_data, ret_sse_data, drawdown_data, pnl_bar_data,
    daily_returns_data, symbol, symbols_data (multi-stock K-line dict).
    """
    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    initial = ctx.portfolio.starting_cash
    start = ctx.start_date
    end = ctx.end_date

    # Collect traded securities
    securities = set()
    for t in trade_log:
        securities.add(t["security"])
    if not securities and ctx.universe:
        securities.add(ctx.universe[0])
    if not securities:
        securities.add("601390")
    symbols_list = sorted(securities)
    symbol = symbols_list[0]

    ohlcv_data = result.get("ohlcv_data", {})

    # Compute K-line data for ALL traded securities
    symbols_data = {}
    for sym in symbols_list:
        symbols_data[sym] = _compute_symbol_kline(sym, start, end, ohlcv_data, trade_log)

    # Primary symbol data (first traded stock) for backward compatibility
    primary = symbols_data[symbol]

    # Cumulative return, daily P&L, daily return
    cum_return_data = _build_return_series(recorded, initial)
    pnl_bar_data, daily_returns_data = _build_daily_pnl(recorded, initial)

    # Benchmark cumulative returns
    ret_hs300 = result.get("chart_index_hs300") if isinstance(result.get("chart_index_hs300"), list) else None
    if not ret_hs300:
        ret_hs300 = _fetch_index_returns("sh000300", start, end, recorded)
    ret_sse = result.get("chart_index_sse") if isinstance(result.get("chart_index_sse"), list) else None
    if not ret_sse:
        ret_sse = _fetch_index_returns("sh000001", start, end, recorded)

    # Drawdown series
    drawdown_data = []
    if cum_return_data:
        peak = cum_return_data[0]["value"]
        for d in cum_return_data:
            if d["value"] > peak: peak = d["value"]
            drawdown_data.append({"time": d["time"], "value": round(d["value"] - peak, 3)})

    return {
        "symbol": symbol,
        "symbols_list": symbols_list,
        "symbols_data": symbols_data,
        "candlestick_data": primary["candlestick_data"],
        "volume_data": primary["volume_data"],
        "ma5_data": primary["ma5_data"], "ma20_data": primary["ma20_data"], "ma60_data": primary["ma60_data"],
        "support_data": primary["support_data"], "resistance_data": primary["resistance_data"],
        "rsi_data": primary["rsi_data"], "macd_data": primary["macd_data"],
        "macd_signal_data": primary["macd_signal_data"], "macd_hist_data": primary["macd_hist_data"],
        "bb_upper_data": primary["bb_upper_data"], "bb_middle_data": primary["bb_middle_data"],
        "bb_lower_data": primary["bb_lower_data"],
        "markers": primary["markers"],
        "cum_return_data": cum_return_data,
        "ret_hs300_data": ret_hs300 if ret_hs300 else [],
        "ret_sse_data": ret_sse if ret_sse else [],
        "drawdown_data": drawdown_data,
        "pnl_bar_data": pnl_bar_data,
        "daily_returns_data": daily_returns_data,
        "tech_stats": primary["tech_stats"],
    }


def _calc_strategy_score(analytics):
    """Compute grade info for HTML/MD report display.

    Wraps grade_strategy() from attribution with graceful fallback.
    """
    from eqlib.attribution import grade_strategy
    try:
        return grade_strategy(analytics)
    except Exception:
        return {"overall": "N/A", "score": 0, "dimensions": [],
                "weakest": "", "strongest": "", "summary_text": ""}


def generate_html_report(result, out_path):
    """Generate interactive HTML report with TradingView lightweight-charts.

    Features: K-line with volume, support/resistance, pivot levels,
    strategy vs 沪深300 vs 上证指数 (cumulative return %),
    drawdown, daily P&L, daily return, trade calendar.
    """
    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    start = ctx.start_date
    end = ctx.end_date
    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    # Compute all chart data arrays (shared with generate_report_json)
    chart = _compute_chart_data(result)
    symbol = chart["symbol"]
    candlestick_data = chart["candlestick_data"]
    ma5_data, ma20_data, ma60_data = chart["ma5_data"], chart["ma20_data"], chart["ma60_data"]
    volume_data = chart["volume_data"]
    support_data, resistance_data = chart["support_data"], chart["resistance_data"]
    rsi_data = chart["rsi_data"]
    macd_data = chart["macd_data"]
    macd_signal_data = chart["macd_signal_data"]
    macd_hist_data = chart["macd_hist_data"]
    bb_upper_data = chart["bb_upper_data"]
    bb_middle_data = chart["bb_middle_data"]
    bb_lower_data = chart["bb_lower_data"]
    markers = chart["markers"]
    cum_return_data = chart["cum_return_data"]
    ret_hs300 = chart["ret_hs300_data"]
    ret_sse = chart["ret_sse_data"]
    drawdown_data = chart["drawdown_data"]
    pnl_bar_data = chart["pnl_bar_data"]
    daily_returns_data = chart["daily_returns_data"]

    dd_hs300 = _build_drawdown_from_cumulative_pct(ret_hs300)
    dd_sse = _build_drawdown_from_cumulative_pct(ret_sse)

    # Benchmark data for metrics calculation
    bench_data = _fetch_benchmark_returns(benchmark, start, end, recorded)

    # ============================================================
    # Performance metrics
    # ============================================================
    metrics = _calc_metrics(result, bench_data)

    # ============================================================
    # Trade log table
    # ============================================================
    trade_rows = ""
    for i, t in enumerate(trade_log, 1):
        action_color = "#26a69a" if t["type"] == "BUY" else "#ef5350"
        action_text = "买入" if t["type"] == "BUY" else "卖出"
        trade_rows += (
            f'<tr>'
            f'<td>{i}</td>'
            f'<td>{html.escape(str(t["date"]))}</td>'
            f'<td style="color:{action_color};font-weight:bold">{action_text}</td>'
            f'<td>{html.escape(str(t["security"]))}</td>'
            f'<td>{t["price"]:.3f}</td>'
            f'<td>{t["amount"]:,}</td>'
            f'<td>{t.get("commission", 0):.2f}</td>'
            f'</tr>\n'
        )

    # ============================================================
    # Trade calendar
    # ============================================================
    trade_map = {}
    for t in trade_log:
        d = _to_tv_date(t["date"])
        if d not in trade_map:
            trade_map[d] = []
        action_text = "买入" if t["type"] == "BUY" else "卖出"
        trade_map[d].append(f"{action_text} {html.escape(str(t['security']))} {t['amount']}股 @{t['price']:.3f}")

    calendar_rows = ""
    if cum_return_data:
        ret_by_date = {d["time"]: d["value"] for d in cum_return_data}
        dd_by_date = {d["time"]: d["value"] for d in drawdown_data}
        for d in sorted(ret_by_date.keys()):
            ops = trade_map.get(d, [])
            if ops:
                op_parts = []
                for o in ops:
                    op_color = "#26a69a" if "买入" in o else "#ef5350"
                    op_parts.append(f'<span style="color:{op_color}">{html.escape(o)}</span>')
                op_html = "<br>".join(op_parts)
                bg = "#1a2332"
            else:
                op_html = '<span style="color:#484f58">—</span>'
                bg = "transparent"

            ret_val = ret_by_date.get(d)
            dd_val = dd_by_date.get(d)
            ret_str = f"{ret_val:+.2f}%" if ret_val is not None else "—"
            dd_str = f"{dd_val:+.2f}%" if dd_val is not None else "—"
            ret_color = "#26a69a" if (ret_val is not None and ret_val >= 0) else "#ef5350"
            dd_color = "#c9d1d9" if (dd_val is None or dd_val == 0) else "#ef5350"

            calendar_rows += (
                f'<tr style="background:{bg}">'
                f'<td>{d}</td>'
                f'<td style="color:{ret_color}">{ret_str}</td>'
                f'<td style="color:{dd_color}">{dd_str}</td>'
                f'<td>{op_html}</td>'
                f'</tr>\n'
            )

    # ============================================================
    # Positions
    # ============================================================
    positions_html = ""
    if ctx.portfolio.positions:
        for sec, pos in ctx.portfolio.positions.items():
            if pos.amount > 0:
                positions_html += (
                    f'<li><b>{html.escape(sec)}</b>: {pos.amount} 股, 均价={pos.avg_cost:.3f}</li>'
                )
    if not positions_html:
        positions_html = "<li>空仓（无持仓）</li>"

    # ============================================================
    # Summary
    # ============================================================
    pnl_color = "#26a69a" if pnl >= 0 else "#ef5350"
    buy_count = sum(1 for t in trade_log if t["type"] == "BUY")
    sell_count = sum(1 for t in trade_log if t["type"] == "SELL")

    # ============================================================
    # Technical summary stats (computed by _compute_chart_data)
    # ============================================================
    tech_stats = chart.get("tech_stats", {})

    # ============================================================
    # Build HTML
    # ============================================================
    bench_code = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    bench_label = {"000300": "沪深300", "000001": "上证指数"}.get(bench_code, bench_code)
    # E2: Escape benchmark name for safe HTML and JavaScript embedding
    bench_label = html.escape(bench_label)
    pnl_badge_class = "pos" if pnl >= 0 else "neg"

    # Grade data for new template (reuse cached analytics from _calc_metrics)
    grade_data = metrics.get("grade_data") or {"overall": "N/A", "score": 0,
                                                "dimensions": [], "summary_text": ""}
    grade_overall = grade_data.get("overall", "N/A")
    grade_score = grade_data.get("score", 0)
    grade_summary = grade_data.get("summary_text", "")
    grade_dims_json = json.dumps(grade_data.get("dimensions", []))

    # Reuse raw analytics from _calc_metrics (no redundant analyze_returns call)
    _ar = metrics.get("_raw_analytics")

    # Monthly returns
    monthly_returns = _ar.get("monthly_returns", {}) if _ar else {}
    monthly_returns_json = json.dumps(monthly_returns)

    # Rolling metrics
    rolling_sharpe_json = json.dumps(_ar.get("rolling_sharpe_60d", []) if _ar else [])
    rolling_vol_json = json.dumps(_ar.get("rolling_volatility_60d", []) if _ar else [])

    # Daily returns stats
    daily_stats = _ar.get("daily_returns_stats", {}) if _ar else {}
    daily_stats_json = json.dumps(daily_stats)

    # Drawdown periods
    dd_periods_json = json.dumps(_ar.get("drawdown_periods", []) if _ar else [])

    html_report = _HTML_TEMPLATE.format(
        html_brand_lockup=html_header_brand_lockup(),
        html_footer_brand=html_footer_brand_chip(),
        symbol=html.escape(str(symbol)),
        start_date=str(start),
        end_date=str(end),
        initial_capital=f"{initial:,.2f}",
        final_value=f"{final:,.2f}",
        pnl=f"{pnl:+,.2f}",
        pnl_pct=f"{pnl_pct:+.2f}%",
        pnl_color=pnl_color,
        pnl_badge_class=pnl_badge_class,
        buy_count=buy_count,
        sell_count=sell_count,
        candlestick_json=json.dumps(candlestick_data),
        ma5_json=json.dumps(ma5_data),
        ma20_json=json.dumps(ma20_data),
        ma60_json=json.dumps(ma60_data),
        volume_json=json.dumps(volume_data),
        markers_json=json.dumps(markers),
        support_json=json.dumps(support_data),
        resistance_json=json.dumps(resistance_data),
        rsi_json=json.dumps(rsi_data),
        macd_json=json.dumps(macd_data),
        macd_signal_json=json.dumps(macd_signal_data),
        macd_hist_json=json.dumps(macd_hist_data),
        bb_upper_json=json.dumps(bb_upper_data),
        bb_middle_json=json.dumps(bb_middle_data),
        bb_lower_json=json.dumps(bb_lower_data),
        cum_return_json=json.dumps(cum_return_data),
        ret_hs300_json=json.dumps(ret_hs300),
        ret_sse_json=json.dumps(ret_sse),
        dd_hs300_json=json.dumps(dd_hs300),
        dd_sse_json=json.dumps(dd_sse),
        drawdown_json=json.dumps(drawdown_data),
        pnl_bar_json=json.dumps(pnl_bar_data),
        daily_returns_json=json.dumps(daily_returns_data),
        trade_rows=trade_rows or '<tr><td colspan="7">未执行任何交易</td></tr>',
        calendar_rows=calendar_rows,
        positions_html=positions_html,
        sharpe=metrics["sharpe"],
        sortino=metrics["sortino"],
        max_dd=metrics["max_dd"],
        max_dd_pct=metrics["max_dd_pct"],
        ann_ret=metrics["ann_ret"],
        ann_ret_pct=metrics["ann_ret_pct"],
        win_rate=metrics["win_rate"],
        benchmark_name=bench_label,
        benchmark_ret=metrics["benchmark_ret"],
        benchmark_ret_pct=metrics["benchmark_ret_pct"],
        alpha=metrics["alpha"],
        beta=metrics["beta"],
        excess_return=metrics["excess_return"],
        calmar=metrics["calmar"],
        profit_loss_ratio=metrics["profit_loss_ratio"],
        daily_excess=metrics["daily_excess"],
        excess_max_dd=metrics["excess_max_dd"],
        excess_sharpe=metrics["excess_sharpe"],
        daily_win_rate=metrics["daily_win_rate"],
        win_count=metrics["win_count"],
        loss_count=metrics["loss_count"],
        info_ratio=metrics["info_ratio"],
        ann_vol=metrics["ann_vol"],
        bm_vol=metrics["bm_vol"],
        trade_count=metrics["trade_count"],
        tech_json=json.dumps(tech_stats),
        symbols_data_json=json.dumps({sym: data for sym, data in chart.get("symbols_data", {}).items()}),
        symbols_list_json=json.dumps(chart.get("symbols_list", [symbol])),
        grade_overall=grade_overall,
        grade_score=f"{grade_score:.0f}",
        grade_summary=html.escape(grade_summary),
        grade_dims_json=grade_dims_json,
        monthly_returns_json=monthly_returns_json,
        rolling_sharpe_json=rolling_sharpe_json,
        rolling_vol_json=rolling_vol_json,
        daily_stats_json=daily_stats_json,
        dd_periods_json=dd_periods_json,
    )

    with open(out_path, "w") as f:
        f.write(html_report)

    print(f"HTML报告已保存: {out_path}")


def _compute_atr(high, low, close, period=14):
    """Compute ATR (Average True Range)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr.iloc[-1] if not atr.empty else None


def _calc_metrics(result, bench_data):
    """Calculate performance metrics using analyze_returns for consistency.

    Returns a dict of formatted metric values for the HTML report template.
    """
    from eqlib.attribution import analyze_returns

    analytics = analyze_returns(result)
    if analytics is None:
        return {
            "sharpe": "N/A", "sortino": "N/A", "max_dd": "N/A", "max_dd_pct": "N/A",
            "ann_ret": "N/A", "ann_ret_pct": "N/A", "win_rate": "N/A",
            "benchmark_ret": "N/A", "benchmark_ret_pct": "N/A",
            "alpha": "N/A", "beta": "N/A",
            "excess_return": "N/A", "excess_return_pct": "N/A",
            "calmar": "N/A", "info_ratio": "N/A",
            "excess_max_dd": "N/A", "excess_sharpe": "N/A",
            "daily_excess": "N/A",
            "profit_loss_ratio": "N/A",
            "win_count": "0", "loss_count": "0",
            "daily_win_rate": "N/A",
            "ann_vol": "N/A", "bm_vol": "N/A",
            "trade_count": "0",
            "grade_data": None,
            "_raw_analytics": None,
        }

    total_ret = analytics["total_return"]
    ann_ret = analytics["annual_return"]
    bench_ret = analytics.get("benchmark_return", 0.0)
    excess_ret = analytics.get("excess_return", total_ret - bench_ret)

    return {
        "sharpe": f"{analytics['sharpe_ratio']:.2f}",
        "sortino": f"{analytics['sortino_ratio']:.2f}",
        "max_dd": f"{analytics['max_drawdown']:.2%}",
        "max_dd_pct": f"{analytics['max_drawdown']:+.2f}%",
        "ann_ret": f"{ann_ret:.2%}",
        "ann_ret_pct": f"{ann_ret:+.2f}%",
        "win_rate": f"{analytics['win_rate_trade']:.0%}",
        "daily_win_rate": f"{analytics['win_rate_daily']:.1%}",
        "benchmark_ret": f"{bench_ret:.2%}",
        "benchmark_ret_pct": f"{bench_ret:+.2f}%",
        "alpha": f"{analytics['alpha']:+.2%}",
        "beta": f"{analytics['beta']:.3f}",
        "excess_return": f"{excess_ret:.2%}",
        "excess_return_pct": f"{excess_ret:+.2f}%",
        "calmar": f"{analytics['calmar_ratio']:.2f}",
        "info_ratio": f"{analytics['information_ratio']:.2f}",
        "excess_max_dd": f"{analytics.get('excess_return_max_drawdown', 0):.2%}",
        "excess_sharpe": f"{analytics.get('excess_return_sharpe', 0):.2f}",
        "daily_excess": f"{analytics.get('daily_excess_return', 0):+.4%}",
        "profit_loss_ratio": ("∞" if analytics.get('profit_loss_ratio', 0) == float('inf')
                              else f"{analytics.get('profit_loss_ratio', 0):.2f}"),
        "win_count": str(analytics.get("win_count", 0)),
        "loss_count": str(analytics.get("loss_count", 0)),
        "ann_vol": f"{analytics['annual_volatility']:.2%}",
        "bm_vol": f"{analytics.get('benchmark_volatility', 0):.2%}",
        "trade_count": str(analytics.get("trade_count", 0)),
        # For benchmark return chart (configured benchmark cumulative return %)
        "bench_last": f"{bench_data[-1]['value'] if bench_data else 0:.2f}",
        # Grade data for HTML template
        "grade_data": _calc_strategy_score(analytics),
        # Raw analytics for HTML template (avoid redundant analyze_returns call)
        "_raw_analytics": analytics,
    }


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EasyQuant | 回测报告 · {symbol}</title>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<script>
if (typeof LightweightCharts === 'undefined') {{
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
  document.head.appendChild(s);
}}
</script>
<style>
/* ================================================================
   DARK BLOOMBERG THEME — CSS VARIABLES
   ================================================================ */
:root {{
  --bg: #0c1222;
  --bg-card: #131b2e;
  --bg-elevated: #1a2438;
  --border: #1e2a3a;
  --border-light: #253042;
  --text-primary: #e2e8f0;
  --text-secondary: #8b98a9;
  --text-dim: #4a5568;
  --up: #26a69a;
  --down: #ef5350;
  --accent: #5b8def;
  --warning: #faad14;
  --shadow: 0 2px 8px rgba(0,0,0,.35);
  --radius: 6px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: var(--bg); color: var(--text-primary); font-size: 13px; line-height: 1.6;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{ background: var(--bg-elevated); padding: 1px 5px; border-radius: 3px; font-size: 12px; color: var(--accent); }}

/* ================================================================
   HEADER
   ================================================================ */
.header {{
  background: var(--bg-card); border-bottom: 1px solid var(--border);
  padding: 12px 0; box-shadow: var(--shadow); position: sticky; top: 0; z-index: 100;
}}
.header-inner {{
  max-width: 98vw; margin: 0 auto; padding: 0 20px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
}}
.eq-brand {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; text-decoration: none; color: inherit; }}
.eq-brand:hover {{ opacity: 0.88; }}
.eq-brand svg {{ display: block; flex-shrink: 0; }}
.eq-brand-text {{ display: flex; flex-direction: column; line-height: 1.15; }}
.eq-brand-name {{ font-size: 15px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.04em; }}
.eq-brand-tag {{ font-size: 9px; font-weight: 500; color: var(--text-dim); letter-spacing: 0.06em; text-transform: uppercase; }}
.header-main {{ flex: 1; min-width: 0; }}
h1 {{ font-size: 16px; font-weight: 600; color: var(--text-primary); }}
h1 .sym {{ color: var(--accent); }}
.header-meta {{ font-size: 11px; color: var(--text-dim); margin-top: 2px; }}
.pnl-badge {{
  padding: 5px 14px; border-radius: 4px; font-size: 13px; font-weight: 600;
  font-variant-numeric: tabular-nums;
}}
.pnl-badge.pos {{ background: rgba(38,166,154,.12); color: var(--up); }}
.pnl-badge.neg {{ background: rgba(239,83,80,.12); color: var(--down); }}
.eq-footer-brand {{ display: inline-flex; align-items: center; gap: 6px; vertical-align: middle; }}
.eq-footer-name {{ font-weight: 600; color: var(--text-secondary); }}

/* ================================================================
   CONTAINER
   ================================================================ */
.container {{ max-width: 98vw; margin: 0 auto; padding: 16px 20px 48px; }}

/* ================================================================
   HERO — GRADE BADGE
   ================================================================ */
.hero {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 28px 32px; margin-bottom: 16px; display: flex; align-items: center; gap: 32px;
  box-shadow: var(--shadow);
}}
.grade-badge {{
  width: 96px; height: 96px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-size: 42px; font-weight: 800; flex-shrink: 0;
  letter-spacing: -0.02em; border: 3px solid;
}}
.grade-S {{ background: rgba(38,166,154,.15); color: #26a69a; border-color: #26a69a; }}
.grade-A {{ background: rgba(91,141,239,.15); color: #5b8def; border-color: #5b8def; }}
.grade-B {{ background: rgba(250,173,20,.15); color: #faad14; border-color: #faad14; }}
.grade-C {{ background: rgba(255,152,0,.15); color: #ff9800; border-color: #ff9800; }}
.grade-D {{ background: rgba(239,83,80,.15); color: #ef5350; border-color: #ef5350; }}
.grade-N\/A {{ background: rgba(74,85,104,.15); color: #4a5568; border-color: #4a5568; }}
.hero-info {{ flex: 1; min-width: 0; }}
.hero-score {{ font-size: 28px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px; }}
.hero-score span {{ font-size: 14px; color: var(--text-dim); font-weight: 400; }}
.hero-summary {{ font-size: 13px; color: var(--text-secondary); line-height: 1.6; }}
.hero-radar {{ width: 160px; height: 160px; flex-shrink: 0; }}

/* ================================================================
   CORE METRIC CARDS (4 prominent)
   ================================================================ */
.core-metrics {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;
}}
.core-card {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px 16px; text-align: center; box-shadow: var(--shadow);
  cursor: pointer; transition: border-color .2s, background .2s;
}}
.core-card:hover {{ border-color: var(--accent); background: var(--bg-elevated); }}
.core-card .cc-label {{ font-size: 11px; color: var(--text-dim); margin-bottom: 6px; font-weight: 500; }}
.core-card .cc-val {{
  font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums;
}}
.core-card .cc-sub {{ font-size: 11px; color: var(--text-dim); margin-top: 2px; font-variant-numeric: tabular-nums; }}
.core-card .cc-grade {{ margin-top: 4px; }}

/* ================================================================
   METRIC CARDS (all metrics grid)
   ================================================================ */
.section-title {{
  font-size: 13px; font-weight: 600; color: var(--text-primary);
  padding: 10px 0 8px; border-bottom: 1px solid var(--border); margin-bottom: 10px;
}}
.metrics-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0; margin-bottom: 14px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow);
}}
.metric-card {{
  padding: 12px 10px; text-align: center;
  border-right: 1px solid var(--border); cursor: pointer; transition: background .15s;
}}
.metric-card:last-child {{ border-right: none; }}
.metric-card:hover {{ background: var(--bg-elevated); }}
.metric-card .title-row {{ display: flex; align-items: center; justify-content: center; gap: 3px; margin-bottom: 4px; }}
.metric-card .mc-title {{ font-size: 10px; color: var(--text-dim); font-weight: 500; }}
.mc-info {{ display: none; }}
.metric-card .mc-val {{
  font-size: 16px; font-weight: 600; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}}
.metric-card .mc-val.pos {{ color: var(--up); }}
.metric-card .mc-val.neg {{ color: var(--down); }}
.mc-grade-row {{ margin-top: 3px; min-height: 14px; }}
.mc-grade {{
  display: inline-block; font-size: 9px; font-weight: 500;
  padding: 1px 5px; border-radius: 3px;
}}
.grade-excellent {{ background: rgba(38,166,154,.12); color: var(--up); }}
.grade-good      {{ background: rgba(91,141,239,.12); color: var(--accent); }}
.grade-fair      {{ background: rgba(250,173,20,.12); color: var(--warning); }}
.grade-poor      {{ background: rgba(239,83,80,.12); color: var(--down); }}
.metrics-grid-secondary {{ grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }}

/* ================================================================
   CHART PANELS
   ================================================================ */
.chart-panel {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 12px; overflow: hidden; box-shadow: var(--shadow); position: relative;
}}
.chart-panel-head {{
  padding: 10px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}}
.chart-panel-head h2 {{ font-size: 13px; font-weight: 600; color: var(--text-primary); }}
.chart-tabs {{ display: flex; gap: 0; }}
.chart-tab {{
  padding: 3px 10px; font-size: 11px; color: var(--text-dim);
  cursor: pointer; border: 1px solid var(--border); border-radius: 3px;
  margin-left: -1px; transition: all .15s; background: transparent;
}}
.chart-tab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.chart-tab:hover:not(.active) {{ background: var(--bg-elevated); color: var(--text-secondary); }}
.chart-body {{ padding: 0; }}
.chart-body .desc {{
  padding: 8px 16px; font-size: 11px; color: var(--text-dim);
  border-bottom: 1px solid var(--border); line-height: 1.5;
}}
#kline    {{ width: 100%; height: 480px; }}
#returns  {{ width: 100%; height: 300px; }}
#drawdown {{ width: 100%; height: 160px; }}
#pnlbar   {{ width: 100%; height: 160px; }}
#dailyret {{ width: 100%; height: 160px; }}
#rsichart  {{ width: 100%; height: 160px; }}
#macdchart {{ width: 100%; height: 160px; }}
#rollingChart {{ width: 100%; height: 260px; }}

/* Indicator toggle panel */
.indicator-panel {{
  position: absolute; top: 8px; left: 8px; z-index: 10;
  display: flex; gap: 4px;
}}
.ind-btn {{
  padding: 4px 10px; font-size: 11px; font-weight: 500;
  border: 1px solid var(--border-light); border-radius: 3px;
  background: rgba(19,27,46,.85); color: var(--text-dim);
  cursor: pointer; transition: all .15s; backdrop-filter: blur(4px);
}}
.ind-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.ind-btn:hover:not(.active) {{ background: var(--bg-elevated); color: var(--text-secondary); }}

/* Crosshair legend */
.chart-legend {{
  position: absolute; top: 8px; right: 70px; z-index: 10;
  background: rgba(19,27,46,.92); border: 1px solid var(--border-light);
  border-radius: 4px; padding: 6px 10px; font-size: 11px;
  font-family: "SF Mono", "Menlo", monospace; line-height: 1.6;
  color: var(--text-secondary); pointer-events: none;
  backdrop-filter: blur(4px); min-width: 200px;
  box-shadow: 0 2px 8px rgba(0,0,0,.3);
  display: none;
}}
.chart-legend.visible {{ display: block; }}
.chart-legend .leg-date {{ font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }}
.chart-legend .leg-row {{ display: flex; justify-content: space-between; gap: 12px; }}
.chart-legend .leg-label {{ color: var(--text-dim); }}
.chart-legend .leg-val {{ font-variant-numeric: tabular-nums; }}
.leg-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}

/* Legend */
.legend {{ display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); align-items: center; flex-wrap: wrap; }}
.legend span {{ display: flex; align-items: center; gap: 4px; }}
.legend .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.legend .ln {{ width: 16px; height: 2px; display: inline-block; }}

/* ================================================================
   TABBED SECTION (Cumulative / Monthly / Rolling / Distribution)
   ================================================================ */
.tabbed-section {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 14px; box-shadow: var(--shadow); overflow: hidden;
}}
.tabbed-section .section-title {{ padding: 12px 16px 0; margin-bottom: 0; border-bottom: none; }}
.tab-bar {{ display: flex; border-bottom: 1px solid var(--border); padding: 0 16px; }}
.tab {{
  padding: 10px 16px; font-size: 13px; color: var(--text-dim);
  cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s;
}}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.tab:hover:not(.active) {{ color: var(--text-secondary); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Monthly heatmap */
.monthly-heatmap {{
  display: grid; gap: 3px; padding: 16px; font-size: 12px;
  grid-template-columns: 60px repeat(12, 1fr);
}}
.mh-header {{ color: var(--text-dim); font-weight: 500; text-align: center; padding: 4px 0; }}
.mh-year {{ color: var(--text-secondary); font-weight: 600; padding: 6px 4px; text-align: right; }}
.mh-cell {{
  text-align: center; padding: 6px 2px; border-radius: 3px;
  font-variant-numeric: tabular-nums; font-weight: 500; font-size: 11px;
}}

/* Distribution canvas */
#distCanvas {{ width: 100%; height: 260px; display: block; }}

/* ================================================================
   DRAWDOWN TABLE
   ================================================================ */
.dd-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.dd-table th {{
  text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
  color: var(--text-dim); font-weight: 500; font-size: 12px;
}}
.dd-table td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text-secondary); }}
.dd-table tr:hover td {{ background: var(--bg-elevated); }}
.dd-depth {{ color: var(--down); font-weight: 600; }}

/* ================================================================
   TRADE TABLE / CALENDAR
   ================================================================ */
.section {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; margin-bottom: 14px; box-shadow: var(--shadow);
}}
.trade-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.trade-table th {{
  text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
  color: var(--text-dim); font-weight: 500; font-size: 12px;
}}
.trade-table td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text-secondary); }}
.trade-table tr:hover td {{ background: var(--bg-elevated); }}
.cal-wrapper {{ max-height: 400px; overflow-y: auto; }}
.cal-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
.cal-table th {{
  text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border);
  color: var(--text-dim); font-weight: 500; font-size: 12px; position: sticky; top: 0;
  background: var(--bg-card); z-index: 1;
}}
.cal-table td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 12px; color: var(--text-secondary); }}
.positions ul {{ list-style: none; padding: 0; }}
.positions li {{ padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text-secondary); }}
.positions li:last-child {{ border-bottom: none; }}

/* ================================================================
   DETAILS / SUMMARY (collapsible)
   ================================================================ */
details {{ margin-bottom: 14px; }}
details summary {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: 600;
  color: var(--text-primary); box-shadow: var(--shadow); transition: background .15s;
  list-style: none;
}}
details summary::-webkit-details-marker {{ display: none; }}
details summary::before {{ content: '▸ '; color: var(--accent); transition: transform .2s; }}
details[open] summary::before {{ content: '▾ '; }}
details summary:hover {{ background: var(--bg-elevated); }}
details .detail-body {{
  background: var(--bg-card); border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 var(--radius) var(--radius); padding: 16px;
}}

/* ================================================================
   MODAL
   ================================================================ */
.modal-overlay {{
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  z-index: 2000; display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; transition: opacity .2s;
}}
.modal-overlay.open {{ opacity: 1; pointer-events: all; }}
.modal {{
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 24px;
  max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,.4); position: relative;
}}
.modal-close {{
  position: absolute; top: 12px; right: 12px; background: none; border: none;
  color: var(--text-dim); font-size: 20px; cursor: pointer;
}}
.modal h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; padding-right: 24px; color: var(--text-primary); }}
.modal-cur {{ font-size: 28px; font-weight: 600; color: var(--accent); margin-bottom: 16px; }}
.modal-sec {{ margin-bottom: 12px; }}
.modal-sec h4 {{ font-size: 12px; color: var(--text-dim); font-weight: 500; margin-bottom: 4px; }}
.modal-sec p {{ font-size: 13px; color: var(--text-secondary); line-height: 1.7; }}
.modal-formula {{
  font-family: "SF Mono", monospace; font-size: 12px; background: var(--bg-elevated);
  padding: 8px 12px; border-radius: 4px; color: var(--text-primary);
}}
.modal-ref {{ font-size: 11px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 8px; margin-top: 8px; }}

/* ================================================================
   SOURCE CARDS / METHOD LIST
   ================================================================ */
.sources-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px;
}}
.src-card {{
  background: var(--bg-elevated); border-radius: 4px; padding: 14px;
  border-left: 3px solid var(--accent);
}}
.src-card .src-type {{ font-size: 10px; color: var(--accent); font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }}
.src-card .src-name {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text-primary); }}
.src-card .src-desc {{ font-size: 12px; color: var(--text-secondary); line-height: 1.5; }}
.method-list {{ padding-left: 18px; font-size: 13px; color: var(--text-secondary); line-height: 1.8; }}
.method-list li {{ margin-bottom: 6px; }}

/* ================================================================
   TECH STATS
   ================================================================ */
.tech-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px; margin-bottom: 12px;
}}
.tech-card {{
  background: var(--bg-elevated); border-radius: 4px; padding: 10px 12px; text-align: center;
}}
.tech-card .title {{ font-size: 11px; color: var(--text-dim); margin-bottom: 4px; }}
.tech-card .val {{ font-size: 16px; font-weight: 600; color: var(--text-primary); }}

/* ================================================================
   FOOTER
   ================================================================ */
.footer {{
  text-align: center; padding: 20px 0; color: var(--text-dim);
  font-size: 12px; border-top: 1px solid var(--border); margin-top: 16px;
}}
.pos {{ color: var(--up); }}
.neg {{ color: var(--down); }}

/* ================================================================
   RESPONSIVE
   ================================================================ */
@media (max-width: 480px) {{
  #kline    {{ height: 280px !important; }}
  #returns  {{ height: 200px !important; }}
  #drawdown, #pnlbar, #dailyret, #rsichart, #macdchart, #rollingChart {{ height: 120px !important; }}
  .header {{ padding: 8px 0; }}
  .header-inner {{ padding: 0 8px; flex-wrap: wrap; gap: 8px; }}
  .eq-brand-text {{ display: none; }}
  h1 {{ font-size: 14px; }}
  .hero {{ flex-direction: column; text-align: center; padding: 20px 16px; gap: 16px; }}
  .hero-radar {{ width: 120px; height: 120px; }}
  .core-metrics {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
  .core-card .cc-val {{ font-size: 18px; }}
  .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .metrics-grid-secondary {{ grid-template-columns: repeat(2, 1fr); }}
  .monthly-heatmap {{ grid-template-columns: 50px repeat(12, 1fr); font-size: 10px; padding: 8px; }}
  .container {{ padding: 8px 8px 32px; }}
  .footer {{ padding: 12px 0; font-size: 10px; }}
  .tab-bar {{ flex-wrap: wrap; }}
  .tab {{ padding: 8px 12px; font-size: 12px; }}
  .tech-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .sources-grid {{ grid-template-columns: 1fr; }}
  .chart-legend {{ top: 4px; right: 4px; min-width: 150px; font-size: 10px; padding: 4px 8px; }}
  .trade-table {{ font-size: 11px; }}
  .trade-table th, .trade-table td {{ padding: 6px 8px; }}
}}
@media (min-width: 481px) and (max-width: 768px) {{
  #kline    {{ height: 360px !important; }}
  #returns  {{ height: 240px !important; }}
  #drawdown, #pnlbar, #dailyret, #rsichart, #macdchart, #rollingChart {{ height: 140px !important; }}
  .core-metrics {{ grid-template-columns: repeat(2, 1fr); }}
  .metrics-grid {{ grid-template-columns: repeat(3, 1fr); }}
  .metrics-grid-secondary {{ grid-template-columns: repeat(3, 1fr); }}
  .sources-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .tech-grid {{ grid-template-columns: repeat(3, 1fr); }}
  .monthly-heatmap {{ font-size: 11px; }}
}}
</style>
</head>
<body>

<!-- ==================== MODAL ==================== -->
<div class="modal-overlay" id="mdOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&#x2715;</button>
    <h3 id="md-title"></h3>
    <div class="modal-cur" id="md-val"></div>
    <div id="md-body"></div>
  </div>
</div>

<!-- ==================== HEADER ==================== -->
<div class="header">
  <div class="header-inner">
    {html_brand_lockup}
    <div class="header-main">
      <h1>回测报告 &middot; <span class="sym">{symbol}</span></h1>
      <div class="header-meta">
        回测区间 {start_date} &rarr; {end_date}&nbsp;&nbsp;&middot;&nbsp;&nbsp;
        初始资金 &yen;{initial_capital}&nbsp;&nbsp;&middot;&nbsp;&nbsp;期末净值 &yen;{final_value}
      </div>
    </div>
    <span class="pnl-badge {pnl_badge_class}">{pnl} ({pnl_pct})</span>
  </div>
</div>

<div class="container">

  <!-- ==================== HERO SECTION ==================== -->
  <div class="hero">
    <div class="grade-badge grade-{grade_overall}">{grade_overall}</div>
    <div class="hero-info">
      <div class="hero-score">{grade_score}<span> / 100</span></div>
      <div class="hero-summary">{grade_summary}</div>
    </div>
    <svg class="hero-radar" id="radarSvg" viewBox="0 0 160 160"></svg>
  </div>

  <!-- ==================== CORE METRICS (4 prominent) ==================== -->
  <div class="core-metrics">
    <div class="core-card" onclick="showMetric('ann_ret')">
      <div class="cc-label">年化收益率</div>
      <div class="cc-val" id="mv-ann_ret" style="color:{pnl_color}">{ann_ret}</div>
      <div class="cc-sub">{ann_ret_pct}</div>
      <div class="cc-grade" id="grade-ann_ret"></div>
    </div>
    <div class="core-card" onclick="showMetric('sharpe')">
      <div class="cc-label">Sharpe 比率</div>
      <div class="cc-val" id="mv-sharpe">{sharpe}</div>
      <div class="cc-grade" id="grade-sharpe"></div>
    </div>
    <div class="core-card" onclick="showMetric('max_dd')">
      <div class="cc-label">最大回撤</div>
      <div class="cc-val neg" id="mv-max_dd">{max_dd}</div>
      <div class="cc-sub">{max_dd_pct}</div>
      <div class="cc-grade" id="grade-max_dd"></div>
    </div>
    <div class="core-card" onclick="showMetric('win_rate')">
      <div class="cc-label">胜率</div>
      <div class="cc-val" id="mv-win_rate">{win_rate}</div>
      <div class="cc-grade" id="grade-win_rate"></div>
    </div>
  </div>

  <!-- ==================== SUMMARY CARDS ==================== -->
  <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); margin-bottom: 14px;">
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">初始资金</span></div>
      <div class="mc-val">&yen;{initial_capital}</div>
    </div>
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">期末净值</span></div>
      <div class="mc-val">&yen;{final_value}</div>
    </div>
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">总盈亏</span></div>
      <div class="mc-val" style="color:{pnl_color}">{pnl}</div>
    </div>
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">总收益率</span></div>
      <div class="mc-val" style="color:{pnl_color}">{pnl_pct}</div>
    </div>
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">买入次数</span></div>
      <div class="mc-val">{buy_count}</div>
    </div>
    <div class="metric-card">
      <div class="title-row"><span class="mc-title">卖出次数</span></div>
      <div class="mc-val">{sell_count}</div>
    </div>
  </div>

  <!-- ==================== TECH STATS ==================== -->
  <div id="tech-section" style="display:none">
    <div class="section-title">技术指标</div>
    <div class="tech-grid" id="tech-stats"></div>
  </div>

  <!-- ==================== K-LINE CHART ==================== -->
  <div class="chart-panel" style="position:relative">
    <div class="chart-panel-head">
      <div>
        <h2>K 线图 &middot; 技术指标</h2>
        <div style="font-size:11px;color:var(--text-dim);margin-top:2px">日 K 线含 MA/BB/S/R、成交量，买卖信号标记 &middot; 前复权</div>
      </div>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <select id="symbolSelector" onchange="switchSymbol(this.value)" style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text-primary);font-size:12px;cursor:pointer"></select>
        <div class="legend">
          <span><span class="dot" style="background:#ef5350"></span>MA5</span>
          <span><span class="dot" style="background:#5b8def"></span>MA20</span>
          <span><span class="dot" style="background:#ab47bc"></span>MA60</span>
          <span><span class="dot" style="background:#26a69a"></span>买入</span>
          <span><span class="dot" style="background:#ef5350"></span>卖出</span>
        </div>
      </div>
    </div>
    <div class="indicator-panel" id="indPanel">
      <button class="ind-btn active" data-ind="ma" onclick="toggleInd('ma',this)">MA</button>
      <button class="ind-btn" data-ind="bb" onclick="toggleInd('bb',this)">BB</button>
      <button class="ind-btn active" data-ind="vol" onclick="toggleInd('vol',this)">VOL</button>
      <button class="ind-btn" data-ind="sr" onclick="toggleInd('sr',this)">S/R</button>
    </div>
    <div class="chart-legend" id="klineLegend"></div>
    <div id="kline"></div>
  </div>

  <!-- RSI chart -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>RSI(14)</h2>
      <div class="legend">
        <span><span class="ln" style="background:#ab47bc"></span>RSI(14)</span>
        <span style="font-size:11px;color:var(--text-dim)">超卖 &lt;30 / 超买 &gt;70</span>
      </div>
    </div>
    <div id="rsichart"></div>
  </div>

  <!-- MACD chart -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>MACD(12,26,9)</h2>
      <div class="legend">
        <span><span class="ln" style="background:#5b8def"></span>MACD</span>
        <span><span class="ln" style="background:#ffa726"></span>Signal</span>
        <span><span class="dot" style="background:#26a69a"></span>柱状图</span>
      </div>
    </div>
    <div id="macdchart"></div>
  </div>

  <!-- ==================== TABBED ANALYSIS ==================== -->
  <div class="tabbed-section">
    <div class="tab-bar">
      <div class="tab active" data-tab="tb-cumret">累计收益</div>
      <div class="tab" data-tab="tb-monthly">月度收益</div>
      <div class="tab" data-tab="tb-rolling">滚动指标</div>
      <div class="tab" data-tab="tb-dist">收益分布</div>
    </div>

    <!-- Cumulative returns -->
    <div id="tb-cumret" class="tab-content active">
      <div class="chart-body">
        <div class="desc">策略累计收益（%）与<strong>沪深300</strong>、<strong>上证综指</strong>对比；「{benchmark_name} 收益」为 <code>set_benchmark</code> 配置的指数口径。</div>
      </div>
      <div id="returns"></div>
      <div class="legend" style="padding: 8px 16px;">
        <span><span class="ln" style="background:#ef5350"></span>策略</span>
        <span><span class="ln" style="background:#5b8def"></span>沪深300</span>
        <span><span class="ln" style="background:#ffa726"></span>上证指数</span>
        <span><span class="ln" style="background:#ab47bc"></span>超额(相对沪深300)</span>
      </div>
      <div style="padding: 4px 16px 8px;">
        <div class="chart-tabs" id="retTabs" style="display:inline-flex">
          <span class="chart-tab active" onclick="toggleReturnSeries('all',this)">策略+基准</span>
          <span class="chart-tab" onclick="toggleReturnSeries('excess',this)">超额收益</span>
          <span class="chart-tab" onclick="toggleReturnSeries('strategy',this)">仅策略</span>
          <span class="chart-tab" onclick="toggleReturnSeries('benchmark',this)">仅基准</span>
        </div>
      </div>
    </div>

    <!-- Monthly heatmap -->
    <div id="tb-monthly" class="tab-content">
      <div class="monthly-heatmap" id="monthlyHeatmap"></div>
    </div>

    <!-- Rolling metrics -->
    <div id="tb-rolling" class="tab-content">
      <div class="chart-body">
        <div class="desc">60日滚动 Sharpe 比率与年化波动率，反映策略风险收益特征的时变性。</div>
      </div>
      <div id="rollingChart"></div>
    </div>

    <!-- Distribution -->
    <div id="tb-dist" class="tab-content">
      <div class="chart-body">
        <div class="desc">日度收益率分布直方图，观察策略收益的偏度与尾部风险。</div>
      </div>
      <canvas id="distCanvas"></canvas>
    </div>
  </div>

  <!-- ==================== DRAWDOWN CHART ==================== -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>回撤曲线</h2>
    </div>
    <div class="chart-body">
      <div class="desc">策略相对历史峰值的回撤（%），与沪深300、上证综指回撤对比。</div>
    </div>
    <div id="drawdown"></div>
  </div>

  <!-- ==================== DRAWDOWN PERIODS TABLE ==================== -->
  <details>
    <summary>最大回撤区间（Top 5）</summary>
    <div class="detail-body">
      <table class="dd-table">
        <thead><tr><th>#</th><th>起始日期</th><th>结束日期</th><th>恢复日期</th><th>回撤深度</th><th>持续天数</th></tr></thead>
        <tbody id="ddPeriodsBody"></tbody>
      </table>
    </div>
  </details>

  <!-- ==================== DAILY P&L ==================== -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>每日盈亏</h2>
    </div>
    <div class="chart-body">
      <div class="desc">每个交易日的资产净值变动额（元）。</div>
    </div>
    <div id="pnlbar"></div>
  </div>

  <!-- ==================== DAILY RETURNS ==================== -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>每日收益率</h2>
    </div>
    <div class="chart-body">
      <div class="desc">日度收益率分布。</div>
    </div>
    <div id="dailyret"></div>
  </div>

  <!-- ==================== ALL METRICS ==================== -->
  <div class="section-title">绩效指标 <span style="opacity:.45;font-weight:400;font-size:10px">— 点击卡片查看定义与解读</span></div>
  <div class="metrics-grid">
    <div class="metric-card" onclick="showMetric('excess_return')">
      <div class="title-row"><span class="mc-title">超额收益</span></div>
      <div class="mc-val" id="mv-excess_return">{excess_return}</div>
      <div class="mc-grade-row"><div id="grade-excess_return"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('bm_ret')">
      <div class="title-row"><span class="mc-title">{benchmark_name} 收益</span></div>
      <div class="mc-val" id="mv-bm_ret">{benchmark_ret}</div>
      <div style="font-size:10px;color:var(--text-dim)">{benchmark_ret_pct}</div>
      <div class="mc-grade-row"><div id="grade-bm_ret"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('alpha')">
      <div class="title-row"><span class="mc-title">Alpha</span></div>
      <div class="mc-val" id="mv-alpha">{alpha}</div>
      <div class="mc-grade-row"><div id="grade-alpha"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('beta')">
      <div class="title-row"><span class="mc-title">Beta</span></div>
      <div class="mc-val" id="mv-beta">{beta}</div>
      <div class="mc-grade-row"><div id="grade-beta"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('sortino')">
      <div class="title-row"><span class="mc-title">Sortino 比率</span></div>
      <div class="mc-val" id="mv-sortino">{sortino}</div>
      <div class="mc-grade-row"><div id="grade-sortino"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('calmar')">
      <div class="title-row"><span class="mc-title">Calmar 比率</span></div>
      <div class="mc-val" id="mv-calmar">{calmar}</div>
      <div class="mc-grade-row"><div id="grade-calmar"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('profit_loss_ratio')">
      <div class="title-row"><span class="mc-title">盈亏比</span></div>
      <div class="mc-val" id="mv-profit_loss_ratio">{profit_loss_ratio}</div>
      <div class="mc-grade-row"><div id="grade-profit_loss_ratio"></div></div>
    </div>
  </div>

  <div class="section-title">超额与风险详情</div>
  <div class="metrics-grid metrics-grid-secondary">
    <div class="metric-card" onclick="showMetric('daily_excess')">
      <div class="title-row"><span class="mc-title">日均超额收益</span></div>
      <div class="mc-val" id="mv-daily_excess">{daily_excess}</div>
      <div class="mc-grade-row"><div id="grade-daily_excess"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('excess_max_dd')">
      <div class="title-row"><span class="mc-title">超额收益最大回撤</span></div>
      <div class="mc-val neg" id="mv-excess_max_dd">{excess_max_dd}</div>
      <div class="mc-grade-row"><div id="grade-excess_max_dd"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('excess_sharpe')">
      <div class="title-row"><span class="mc-title">超额夏普比率</span></div>
      <div class="mc-val" id="mv-excess_sharpe">{excess_sharpe}</div>
      <div class="mc-grade-row"><div id="grade-excess_sharpe"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('daily_win_rate')">
      <div class="title-row"><span class="mc-title">日胜率</span></div>
      <div class="mc-val" id="mv-daily_win_rate">{daily_win_rate}</div>
      <div class="mc-grade-row"><div id="grade-daily_win_rate"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('win_count')">
      <div class="title-row"><span class="mc-title">盈利次数</span></div>
      <div class="mc-val" id="mv-win_count">{win_count}</div>
      <div class="mc-grade-row"><div id="grade-win_count"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('loss_count')">
      <div class="title-row"><span class="mc-title">亏损次数</span></div>
      <div class="mc-val" id="mv-loss_count">{loss_count}</div>
      <div class="mc-grade-row"><div id="grade-loss_count"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('info_ratio')">
      <div class="title-row"><span class="mc-title">信息比率</span></div>
      <div class="mc-val" id="mv-info_ratio">{info_ratio}</div>
      <div class="mc-grade-row"><div id="grade-info_ratio"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('ann_vol')">
      <div class="title-row"><span class="mc-title">策略波动率</span></div>
      <div class="mc-val" id="mv-ann_vol">{ann_vol}</div>
      <div class="mc-grade-row"><div id="grade-ann_vol"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('bm_vol')">
      <div class="title-row"><span class="mc-title">基准波动率</span></div>
      <div class="mc-val" id="mv-bm_vol">{bm_vol}</div>
      <div class="mc-grade-row"><div id="grade-bm_vol"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('trade_count')">
      <div class="title-row"><span class="mc-title">交易次数</span></div>
      <div class="mc-val" id="mv-trade_count">{trade_count}</div>
      <div class="mc-grade-row"><div id="grade-trade_count"></div></div>
    </div>
  </div>

  <!-- ==================== TRADE DETAILS (collapsible) ==================== -->
  <details>
    <summary>交易明细</summary>
    <div class="detail-body">
      <table class="trade-table">
        <thead><tr>
          <th>#</th><th>日期</th><th>操作</th><th>代码</th>
          <th>价格</th><th>数量</th><th>手续费</th>
        </tr></thead>
        <tbody>{trade_rows}</tbody>
      </table>
    </div>
  </details>

  <!-- ==================== TRADE CALENDAR (collapsible) ==================== -->
  <details>
    <summary>交易日历</summary>
    <div class="detail-body">
      <div class="cal-wrapper">
        <table class="cal-table">
          <thead><tr>
            <th>日期</th><th>累计收益</th><th>回撤</th><th>操作</th>
          </tr></thead>
          <tbody>{calendar_rows}</tbody>
        </table>
      </div>
    </div>
  </details>

  <!-- ==================== POSITIONS (collapsible) ==================== -->
  <details>
    <summary>当前持仓</summary>
    <div class="detail-body positions">
      <ul>{positions_html}</ul>
    </div>
  </details>

  <!-- ==================== DATA SOURCES ==================== -->
  <div class="section">
    <div class="section-title">数据来源与计算方法</div>
    <div class="tab-bar">
      <div class="tab active" data-tab="tb-sources">数据来源</div>
      <div class="tab" data-tab="tb-method">指标计算说明</div>
    </div>
    <div id="tb-sources" class="tab-content active">
      <div class="sources-grid">
        <div class="src-card">
          <div class="src-type">行情数据</div>
          <div class="src-name">AKShare &mdash; 东方财富接口</div>
          <div class="src-desc">A股日线 OHLCV 行情通过 <code>stock_zh_a_hist</code> 获取，<strong>前复权（qfq）</strong>处理。数据由东方财富网提供，仅供研究使用。</div>
        </div>
        <div class="src-card">
          <div class="src-type">基准指数</div>
          <div class="src-name">沪深300（000300）&middot; 上证综指（000001）</div>
          <div class="src-desc">通过 AKShare <code>stock_zh_index_daily_em</code> 获取，以回测起始日收盘价归一化后与策略区间对齐。</div>
        </div>
        <div class="src-card">
          <div class="src-type">无风险利率</div>
          <div class="src-name">固定 3.0% / 年</div>
          <div class="src-desc">参考近年中国国债市场平均利率水平，用于 Sharpe、Sortino、Alpha 等指标计算（日化 = 3% &divide; 252）。</div>
        </div>
        <div class="src-card">
          <div class="src-type">回测引擎</div>
          <div class="src-name">EasyQuant &mdash; eqlib</div>
          <div class="src-desc">基于事件驱动框架，以每日收盘价成交（T+1 制度），含双边手续费与最小交易单位（100股）限制。</div>
        </div>
      </div>
    </div>
    <div id="tb-method" class="tab-content">
      <ul class="method-list">
        <li><strong>年化收益率</strong>(1 + 总收益率)^(252/N) &minus; 1，N 为回测交易日数。</li>
        <li><strong>Sharpe 比率</strong>(日均收益率 &minus; r_f/252) / 日收益率标准差 &times; &radic;252。</li>
        <li><strong>Sortino 比率</strong>同 Sharpe 但分母仅用下行波动率。</li>
        <li><strong>最大回撤</strong>max[(峰值 &minus; 谷值) / 峰值]。</li>
        <li><strong>Calmar 比率</strong>年化收益率 / |最大回撤|。</li>
        <li><strong>Alpha / Beta</strong>基于 CAPM，以沪深300为市场基准。</li>
        <li><strong>胜率</strong>按 FIFO 配对买卖，盈利对数 / 全部配对数。</li>
      </ul>
    </div>
  </div>

</div>

<div class="footer">
  {html_footer_brand}
  &nbsp;&middot;&nbsp; eqlib &nbsp;|&nbsp;
  行情数据：<a href="https://akshare.akfamily.xyz/" target="_blank" rel="noopener noreferrer">AKShare</a>（东方财富）&nbsp;|&nbsp;
  本报告仅供研究参考，不构成任何投资建议。
</div>

<script>
(function() {{

  /* =================================================================
     METRIC DEFINITIONS
     ================================================================= */
  const DEFS = {{
    ann_ret: {{
      name: '年化收益率',
      formula: '(1 + 总收益率) ^ (252 / N) − 1',
      desc: '将回测期间的累计总收益率换算为年化水平，N 为实际回测交易日数。',
      interp: '>15% 优秀，>8% 良好，>0% 正收益，≤0% 亏损。',
      ref: 'Geometric Mean Return Annualization',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 15) return ['excellent', '优秀 >15%'];
        if (n > 8)  return ['good',      '良好 >8%'];
        if (n > 0)  return ['fair',      '正收益'];
        return ['poor', '负收益'];
      }},
    }},
    sharpe: {{
      name: 'Sharpe 比率',
      formula: '(E[R_p] − r_f) / σ_p × √252',
      desc: '衡量每单位总风险所获得的超额年化收益。',
      interp: '>2.0 优秀，>1.0 良好，>0.5 一般，≤0.5 较差。',
      ref: 'Sharpe (1966, 1994).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 2)   return ['excellent', '优秀 >2.0'];
        if (n > 1)   return ['good',      '良好 >1.0'];
        if (n > 0.5) return ['fair',      '一般 >0.5'];
        return ['poor', '较差'];
      }},
    }},
    sortino: {{
      name: 'Sortino 比率',
      formula: '(E[R_p] − r_f) / σ_down × √252',
      desc: '分母仅计算下行波动率，更真实反映投资者面临的实际风险。',
      interp: '>2.0 优秀，>1.0 良好。',
      ref: 'Sortino & Price (1994).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 2)   return ['excellent', '优秀 >2.0'];
        if (n > 1)   return ['good',      '良好 >1.0'];
        if (n > 0.5) return ['fair',      '一般 >0.5'];
        return ['poor', '较差'];
      }},
    }},
    max_dd: {{
      name: '最大回撤',
      formula: 'max[(峰值 − 谷值) / 峰值] × 100%',
      desc: '净值从历史最高点到随后最低点的最大跌幅百分比。',
      interp: '<5% 优秀，<10% 良好，<20% 可接受，>20% 风险偏高。',
      ref: 'Magdon-Ismail & Atiya (2004).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n < 5)  return ['excellent', '优秀 <5%'];
        if (n < 10) return ['good',      '良好 <10%'];
        if (n < 20) return ['fair',      '可接受 <20%'];
        return ['poor', '偏高 >20%'];
      }},
    }},
    win_rate: {{
      name: '胜率',
      formula: '盈利配对交易数 / 全部配对交易数',
      desc: 'FIFO配对中卖出价格高于买入价格的比例。',
      interp: '>60% 优秀，>50% 良好，40-50% 一般。',
      ref: 'Van Tharp (1999).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 60) return ['excellent', '优秀 >60%'];
        if (n > 50) return ['good',      '良好 >50%'];
        if (n > 40) return ['fair',      '一般 >40%'];
        return ['poor', '偏低 <40%'];
      }},
    }},
    alpha: {{
      name: 'Alpha',
      formula: 'α = R_p − [r_f + β × (R_m − r_f)]',
      desc: '基于 CAPM 的年化超额收益。正 Alpha 表明策略创造了附加价值。',
      interp: '>5% 优秀，>0% 有价值，<0% 跑输基准。',
      ref: 'Jensen (1968).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 5)  return ['excellent', '优秀 >5%'];
        if (n > 0)  return ['good',      '正 Alpha'];
        if (n > -5) return ['fair',      '略低'];
        return ['poor', '负 Alpha'];
      }},
    }},
    beta: {{
      name: 'Beta',
      formula: 'β = Cov(R_p, R_m) / Var(R_m)',
      desc: '策略收益率相对市场基准的敏感程度。',
      interp: 'β=1 与市场同步；β>1 放大波动；β<1 减弱波动。',
      ref: 'CAPM: Sharpe (1964).',
      grader(v) {{ return null; }},
    }},
    bm_ret: {{
      name: '{benchmark_name} 收益',
      formula: '(期末收盘价 / 期初收盘价 − 1) × 100%',
      desc: '基准指数在相同回测区间的累计涨跌幅。',
      interp: '将策略收益率与基准对比。',
      ref: '沪深300指数',
      grader(v) {{ return null; }},
    }},
    excess_return: {{
      name: '超额收益',
      formula: '策略总收益率 − 基准总收益率',
      desc: '策略相对基准的绝对超额回报。',
      interp: '>10% 优秀，>0% 正超额，<0% 跑输基准。',
      ref: 'Active Return',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 10) return ['excellent', '优秀 >10%'];
        if (n > 0)  return ['good',      '正超额'];
        return ['poor', '跑输基准'];
      }},
    }},
    calmar: {{
      name: 'Calmar 比率',
      formula: '年化收益率 / |最大回撤|',
      desc: '年化回报相对最大回撤的性价比。',
      interp: '>1.0 优秀，>0.5 良好，<0.3 偏低。',
      ref: 'Young (1991).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 1)   return ['excellent', '优秀 >1.0'];
        if (n > 0.5) return ['good',      '良好 >0.5'];
        return ['fair', '偏低'];
      }},
    }},
    profit_loss_ratio: {{
      name: '盈亏比',
      formula: '平均单笔盈利 / 平均单笔亏损',
      desc: '每笔交易平均盈利与亏损的比率。',
      interp: '>3:1 优秀，>2:1 良好，>1:1 盈利覆盖亏损。',
      ref: 'Van Tharp (1999).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n) || n === 0) return null;
        if (n > 3) return ['excellent', '优秀 >3:1'];
        if (n > 2) return ['good',      '良好 >2:1'];
        if (n > 1) return ['fair',      '盈利覆盖亏损'];
        return ['poor', '亏损大于盈利'];
      }},
    }},
    daily_excess: {{
      name: '日均超额收益',
      formula: 'mean(策略日收益 − 基准日收益) × 252',
      desc: '策略每日超额收益的年化值。',
      interp: '>3% 优秀，>0% 正超额。',
      ref: 'Daily Active Return',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 3)  return ['excellent', '优秀 >3%'];
        if (n > 0)  return ['good',      '正超额'];
        return ['poor', '负超额'];
      }},
    }},
    excess_max_dd: {{
      name: '超额收益最大回撤',
      formula: 'max(超额累积峰值 − 超额累积谷值) / 峰值',
      desc: '超额收益累积曲线的最大回撤。',
      interp: '<5% 优秀，<10% 良好，>15% 偏高。',
      ref: 'Tracking Error Drawdown',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n < 5)  return ['excellent', '优秀 <5%'];
        if (n < 10) return ['good',      '良好 <10%'];
        if (n < 15) return ['fair',      '可接受'];
        return ['poor', '偏高 >15%'];
      }},
    }},
    excess_sharpe: {{
      name: '超额夏普比率',
      formula: '(E[超额日收益] − r_f) / σ(超额日收益) × √252',
      desc: '以超额日收益为输入的 Sharpe 比率。',
      interp: '>1.0 优秀，>0.5 良好。',
      ref: 'Information Ratio variant',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 1)   return ['excellent', '优秀 >1.0'];
        if (n > 0.5) return ['good',      '良好 >0.5'];
        if (n > 0)   return ['fair',      '正超额夏普'];
        return ['poor', '负值'];
      }},
    }},
    daily_win_rate: {{
      name: '日胜率',
      formula: '盈利交易日数 / 总交易日数',
      desc: '策略日度收益为正的比例。',
      interp: '>55% 优秀，>50% 良好。',
      ref: 'Daily Hit Ratio',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 55) return ['excellent', '优秀 >55%'];
        if (n > 50) return ['good',      '良好 >50%'];
        return ['fair', '一般'];
      }},
    }},
    win_count: {{
      name: '盈利次数', formula: '', desc: '盈利配对交易次数。',
      interp: '', ref: '', grader(v) {{ return null; }},
    }},
    loss_count: {{
      name: '亏损次数', formula: '', desc: '亏损配对交易次数。',
      interp: '', ref: '', grader(v) {{ return null; }},
    }},
    info_ratio: {{
      name: '信息比率',
      formula: 'mean(超额日收益) / std(超额日收益) × √252',
      desc: '每单位跟踪误差的主动年化收益。',
      interp: '>0.5 优秀，>0.3 良好。',
      ref: 'Grinold & Kahn (1999).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 0.5) return ['excellent', '优秀 >0.5'];
        if (n > 0.3) return ['good',      '良好 >0.3'];
        if (n > 0)   return ['fair',      '正主动收益'];
        return ['poor', '负值'];
      }},
    }},
    ann_vol: {{
      name: '策略波动率', formula: 'σ(日收益) × √252', desc: '日收益率的年化标准差。',
      interp: '<10% 低波动，10-20% 中等，>20% 高波动。', ref: '', grader(v) {{ return null; }},
    }},
    bm_vol: {{
      name: '基准波动率', formula: 'σ(基准日收益) × √252', desc: '基准日收益率的年化标准差。',
      interp: '与策略波动率对比。', ref: '', grader(v) {{ return null; }},
    }},
    trade_count: {{
      name: '交易次数', formula: '', desc: '回测期间完成的配对买卖总次数。',
      interp: '', ref: '', grader(v) {{ return null; }},
    }},
  }};

  /* =================================================================
     RENDER GRADE BADGES
     ================================================================= */
  function renderGrades() {{
    Object.entries(DEFS).forEach(([key, def]) => {{
      const valEl   = document.getElementById('mv-'    + key);
      const gradeEl = document.getElementById('grade-' + key);
      if (!valEl || !gradeEl || !def.grader) return;
      const result = def.grader(valEl.textContent);
      if (!result) return;
      const [cls, label] = result;
      gradeEl.innerHTML = '<span class="mc-grade grade-' + cls + '">' + label + '</span>';
    }});
  }}

  /* =================================================================
     MODAL
     ================================================================= */
  function showMetric(key) {{
    const def = DEFS[key];
    if (!def) return;
    const valEl = document.getElementById('mv-' + key);
    const val = valEl ? valEl.textContent.trim() : 'N/A';
    document.getElementById('md-title').textContent = def.name;
    document.getElementById('md-val').textContent   = val;
    let body = '';
    if (def.formula)
      body += '<div class="modal-sec"><h4>计算公式</h4><div class="modal-formula">' + def.formula + '</div></div>';
    if (def.desc)
      body += '<div class="modal-sec"><h4>指标说明</h4><p>' + def.desc + '</p></div>';
    if (def.interp)
      body += '<div class="modal-sec"><h4>解读指南</h4><p>' + def.interp + '</p></div>';
    if (def.ref)
      body += '<div class="modal-ref">&#128218; 参考文献：' + def.ref + '</div>';
    document.getElementById('md-body').innerHTML = body;
    document.getElementById('mdOverlay').classList.add('open');
  }}

  function closeModal() {{
    document.getElementById('mdOverlay').classList.remove('open');
  }}

  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

  /* =================================================================
     RADAR CHART (inline SVG, 6 dimensions)
     ================================================================= */
  (function() {{
    const dims = {grade_dims_json};
    if (!dims || dims.length === 0) return;
    const svg = document.getElementById('radarSvg');
    const cx = 80, cy = 80, r = 60;
    const n = dims.length;
    const angleStep = (2 * Math.PI) / n;
    // Draw grid rings
    [0.25, 0.5, 0.75, 1.0].forEach(frac => {{
      let pts = [];
      for (let i = 0; i < n; i++) {{
        const a = -Math.PI/2 + i * angleStep;
        pts.push((cx + r * frac * Math.cos(a)).toFixed(1) + ',' + (cy + r * frac * Math.sin(a)).toFixed(1));
      }}
      const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      poly.setAttribute('points', pts.join(' '));
      poly.setAttribute('fill', 'none');
      poly.setAttribute('stroke', '#1e2a3a');
      poly.setAttribute('stroke-width', '0.5');
      svg.appendChild(poly);
    }});
    // Draw axes + labels
    dims.forEach((d, i) => {{
      const a = -Math.PI/2 + i * angleStep;
      const x2 = cx + r * Math.cos(a);
      const y2 = cy + r * Math.sin(a);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', cx); line.setAttribute('y1', cy);
      line.setAttribute('x2', x2.toFixed(1)); line.setAttribute('y2', y2.toFixed(1));
      line.setAttribute('stroke', '#1e2a3a'); line.setAttribute('stroke-width', '0.5');
      svg.appendChild(line);
      // Label
      const lx = cx + (r + 14) * Math.cos(a);
      const ly = cy + (r + 14) * Math.sin(a);
      const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      txt.setAttribute('x', lx.toFixed(1)); txt.setAttribute('y', (ly + 3).toFixed(1));
      txt.setAttribute('text-anchor', 'middle');
      txt.setAttribute('fill', '#8b98a9'); txt.setAttribute('font-size', '8');
      txt.textContent = d.label || d.name || '';
      svg.appendChild(txt);
    }});
    // Draw data polygon
    let dataPts = [];
    dims.forEach((d, i) => {{
      const a = -Math.PI/2 + i * angleStep;
      const score = Math.max(0, Math.min(100, d.score || 0)) / 100;
      dataPts.push((cx + r * score * Math.cos(a)).toFixed(1) + ',' + (cy + r * score * Math.sin(a)).toFixed(1));
    }});
    const dataPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    dataPoly.setAttribute('points', dataPts.join(' '));
    dataPoly.setAttribute('fill', 'rgba(91,141,239,0.15)');
    dataPoly.setAttribute('stroke', '#5b8def');
    dataPoly.setAttribute('stroke-width', '1.5');
    svg.appendChild(dataPoly);
    // Data dots
    dims.forEach((d, i) => {{
      const a = -Math.PI/2 + i * angleStep;
      const score = Math.max(0, Math.min(100, d.score || 0)) / 100;
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', (cx + r * score * Math.cos(a)).toFixed(1));
      dot.setAttribute('cy', (cy + r * score * Math.sin(a)).toFixed(1));
      dot.setAttribute('r', '3');
      dot.setAttribute('fill', '#5b8def');
      svg.appendChild(dot);
    }});
  }})();

  /* =================================================================
     MONTHLY HEATMAP
     ================================================================= */
  (function() {{
    const mr = {monthly_returns_json};
    const container = document.getElementById('monthlyHeatmap');
    if (!mr || Object.keys(mr).length === 0) {{
      container.innerHTML = '<div style="padding:20px;color:var(--text-dim);grid-column:1/-1;text-align:center">暂无月度收益数据</div>';
      return;
    }}
    const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    // Header row
    container.innerHTML = '<div class="mh-header"></div>' + months.map(m => '<div class="mh-header">' + m + '</div>').join('');
    // Group by year
    const byYear = {{}};
    Object.entries(mr).forEach(([k, v]) => {{
      const [y, m] = k.split('-');
      if (!byYear[y]) byYear[y] = {{}};
      byYear[y][parseInt(m)] = v;
    }});
    Object.keys(byYear).sort().forEach(year => {{
      let row = '<div class="mh-year">' + year + '</div>';
      for (let m = 1; m <= 12; m++) {{
        const val = byYear[year][m];
        if (val === undefined) {{
          row += '<div class="mh-cell">—</div>';
        }} else {{
          const pct = (val * 100).toFixed(1);
          const intensity = Math.min(Math.abs(val) * 5, 1);
          let bg, color;
          if (val >= 0) {{
            bg = 'rgba(38,166,154,' + (0.08 + intensity * 0.35).toFixed(2) + ')';
            color = '#26a69a';
          }} else {{
            bg = 'rgba(239,83,80,' + (0.08 + intensity * 0.35).toFixed(2) + ')';
            color = '#ef5350';
          }}
          row += '<div class="mh-cell" style="background:' + bg + ';color:' + color + '">' + (val >= 0 ? '+' : '') + pct + '%</div>';
        }}
      }}
      container.innerHTML += row;
    }});
  }})();

  /* =================================================================
     DRAWDOWN PERIODS TABLE
     ================================================================= */
  (function() {{
    const periods = {dd_periods_json};
    const tbody = document.getElementById('ddPeriodsBody');
    if (!periods || periods.length === 0) {{
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-dim)">暂无回撤数据</td></tr>';
      return;
    }}
    tbody.innerHTML = periods.map((p, i) => {{
      const depth = (p.depth * 100).toFixed(2);
      const days = p.recovery_days || p.duration_days || '—';
      return '<tr><td>' + (i+1) + '</td><td>' + (p.start || '—') + '</td><td>' + (p.end || '—') +
        '</td><td>' + (p.recovery || '—') + '</td><td class="dd-depth">' + depth + '%</td><td>' + days + '</td></tr>';
    }}).join('');
  }})();

  /* =================================================================
     RETURN DISTRIBUTION HISTOGRAM (Canvas)
     ================================================================= */
  window._drawDistribution = function() {{
    const stats = {daily_stats_json};
    const canvas = document.getElementById('distCanvas');
    if (!stats || !stats.histogram || !canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    const hist = stats.histogram;
    const maxCount = Math.max(...hist.map(b => b.count));
    const barW = (W - 60) / hist.length;
    const chartH = H - 50;
    // Background
    ctx.fillStyle = '#131b2e';
    ctx.fillRect(0, 0, W, H);
    // Bars
    hist.forEach((b, i) => {{
      const h = (b.count / maxCount) * chartH;
      const x = 40 + i * barW;
      const y = H - 30 - h;
      ctx.fillStyle = b.mid >= 0 ? 'rgba(38,166,154,0.7)' : 'rgba(239,83,80,0.7)';
      ctx.fillRect(x, y, barW - 1, h);
    }});
    // Axis labels
    ctx.fillStyle = '#4a5568';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    [0, Math.floor(hist.length/4), Math.floor(hist.length/2), Math.floor(3*hist.length/4), hist.length-1].forEach(i => {{
      if (hist[i]) ctx.fillText((hist[i].mid * 100).toFixed(1) + '%', 40 + i * barW + barW/2, H - 12);
    }});
    // Title
    ctx.fillStyle = '#8b98a9';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('均值: ' + ((stats.mean || 0) * 100).toFixed(3) + '%  标准差: ' + ((stats.std || 0) * 100).toFixed(3) + '%  偏度: ' + (stats.skewness || 0).toFixed(2) + '  峰度: ' + (stats.kurtosis || 0).toFixed(2), 40, 18);
  }};
  window._drawDistribution();

  /* =================================================================
     CHART COMMON OPTIONS (DARK)
     ================================================================= */
  const cmn = {{
    layout: {{
      background: {{ type: 'solid', color: '#131b2e' }},
      textColor: '#8b98a9', fontSize: 11,
      fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif',
    }},
    grid: {{ vertLines: {{ color: '#1e2a3a' }}, horzLines: {{ color: '#1e2a3a' }} }},
    timeScale: {{
      borderColor: '#1e2a3a',
      timeVisible: false,
      barSpacing: 6,
    }},
    rightPriceScale: {{ borderColor: '#1e2a3a' }},
    crosshair: {{
      mode: 1,
      vertLine: {{ color: '#4a5568', width: 1, style: 2, labelBackgroundColor: '#253042' }},
      horzLine: {{ color: '#4a5568', width: 1, style: 2, labelBackgroundColor: '#253042' }},
    }},
  }};

  /* =================================================================
     CHART INITIALIZATION
     ================================================================= */
  var chartError = false;
  try {{
    if (typeof LightweightCharts === 'undefined') {{
      throw new Error('LightweightCharts library not loaded');
    }}

    // Multi-stock K-line data
    var _symbolsData = {symbols_data_json};
    var _symbolsList = {symbols_list_json};

    // Populate stock selector
    (function() {{
      var sel = document.getElementById('symbolSelector');
      if (sel && _symbolsList.length > 1) {{
        _symbolsList.forEach(function(sym) {{
          var opt = document.createElement('option');
          opt.value = sym;
          opt.textContent = sym;
          sel.appendChild(opt);
        }});
      }} else if (sel) {{
        sel.style.display = 'none';
      }}
    }})();

    /* K-line */
    const kEl = document.getElementById('kline');
    const kChart = LightweightCharts.createChart(kEl, {{
      ...cmn, width: kEl.clientWidth, height: 480,
      rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.22 }} }},
    }});
    const cSeries = kChart.addCandlestickSeries({{
      upColor: '#ef5350', downColor: '#26a69a',
      borderUpColor: '#ef5350', borderDownColor: '#26a69a',
      wickUpColor: '#ef5350', wickDownColor: '#26a69a',
    }});
    cSeries.setData({candlestick_json});
    cSeries.setMarkers({markers_json});

    // MA series
    const ma5S = kChart.addLineSeries({{ color: '#ef5350', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    ma5S.setData({ma5_json});
    const ma20S = kChart.addLineSeries({{ color: '#5b8def', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    ma20S.setData({ma20_json});
    const ma60S = kChart.addLineSeries({{ color: '#ab47bc', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    ma60S.setData({ma60_json});

    // Bollinger Bands
    const bbUpperS = kChart.addLineSeries({{ color: 'rgba(91,141,239,0.5)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    bbUpperS.setData({bb_upper_json});
    const bbMiddleS = kChart.addLineSeries({{ color: 'rgba(91,141,239,0.7)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    bbMiddleS.setData({bb_middle_json});
    const bbLowerS = kChart.addLineSeries({{ color: 'rgba(91,141,239,0.5)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    bbLowerS.setData({bb_lower_json});

    // Support/Resistance
    const supS = kChart.addLineSeries({{ color: 'rgba(38,166,154,0.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    supS.setData({support_json});
    const resS = kChart.addLineSeries({{ color: 'rgba(239,83,80,0.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }});
    resS.setData({resistance_json});

    // Volume
    const volS = kChart.addHistogramSeries({{
      priceFormat: {{ type: 'volume' }},
      priceScaleId: 'vol',
    }});
    volS.priceScale().applyOptions({{ scaleMargins: {{ top: 0.8, bottom: 0 }} }});
    volS.setData({volume_json});
    kChart.timeScale().fitContent();

    // RSI/MACD series refs
    var rsiSeries, macdLineSeries, macdSignalSeries, macdHistSeries;

    // Symbol switch
    window.switchSymbol = function(sym) {{
      var d = _symbolsData[sym];
      if (!d) return;
      cSeries.setData(d.candlestick_data || []);
      cSeries.setMarkers(d.markers || []);
      ma5S.setData(d.ma5_data || []);
      ma20S.setData(d.ma20_data || []);
      ma60S.setData(d.ma60_data || []);
      bbUpperS.setData(d.bb_upper_data || []);
      bbMiddleS.setData(d.bb_middle_data || []);
      bbLowerS.setData(d.bb_lower_data || []);
      supS.setData(d.support_data || []);
      resS.setData(d.resistance_data || []);
      volS.setData(d.volume_data || []);
      kChart.timeScale().fitContent();
      if (rsiSeries) rsiSeries.setData(d.rsi_data || []);
      if (macdLineSeries) macdLineSeries.setData(d.macd_data || []);
      if (macdSignalSeries) macdSignalSeries.setData(d.macd_signal_data || []);
      if (macdHistSeries) macdHistSeries.setData(d.macd_hist_data || []);
    }};

    /* Cumulative returns */
    const rEl = document.getElementById('returns');
    const rChart = LightweightCharts.createChart(rEl, {{ ...cmn, width: rEl.clientWidth, height: 300 }});
    const stratLine = rChart.addLineSeries({{
      color: '#ef5350', lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerVisible: true, title: '策略',
    }});
    stratLine.setData({cum_return_json});
    const hs300Line = rChart.addLineSeries({{
      color: '#5b8def', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerVisible: true, title: '沪深300',
    }});
    hs300Line.setData({ret_hs300_json});
    const sseLine = rChart.addLineSeries({{
      color: '#ffa726', lineWidth: 1.5, lineStyle: 2, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerVisible: true, title: '上证指数',
    }});
    sseLine.setData({ret_sse_json});

    /* Excess return vs HS300 */
    const excessLine = rChart.addLineSeries({{
      color: '#ab47bc', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false, title: '超额',
    }});
    var excessReturnData = [];
    if ({cum_return_json}.length > 0 && {ret_hs300_json}.length > 0) {{
      var cumArr = {cum_return_json};
      var hsArr = {ret_hs300_json};
      var hsMap = {{}};
      hsArr.forEach(function(d) {{ hsMap[d.time] = d.value; }});
      cumArr.forEach(function(d) {{
        if (hsMap.hasOwnProperty(d.time)) {{
          excessReturnData.push({{ time: d.time, value: +(d.value - hsMap[d.time]).toFixed(3) }});
        }}
      }});
    }}
    excessLine.setData(excessReturnData);
    rChart.timeScale().fitContent();

    var retVis = {{ strat: true, hs300: true, sse: true, excess: false }};
    window.toggleReturnSeries = function(mode, el) {{
      document.querySelectorAll('#retTabs .chart-tab').forEach(function(t) {{ t.classList.remove('active'); }});
      if (el) el.classList.add('active');
      if (mode === 'all') {{ retVis = {{ strat: true, hs300: true, sse: true, excess: false }}; }}
      else if (mode === 'excess') {{ retVis = {{ strat: true, hs300: false, sse: false, excess: true }}; }}
      else if (mode === 'strategy') {{ retVis = {{ strat: true, hs300: false, sse: false, excess: false }}; }}
      else if (mode === 'benchmark') {{ retVis = {{ strat: false, hs300: true, sse: true, excess: false }}; }}
      stratLine.applyOptions({{ visible: retVis.strat }});
      hs300Line.applyOptions({{ visible: retVis.hs300 }});
      sseLine.applyOptions({{ visible: retVis.sse }});
      excessLine.applyOptions({{ visible: retVis.excess }});
    }};

    /* RSI(14) */
    const rsiEl = document.getElementById('rsichart');
    const rsiChart = LightweightCharts.createChart(rsiEl, {{
      ...cmn, width: rsiEl.clientWidth, height: 160,
      rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.05 }} }},
    }});
    const rsiLine = rsiChart.addLineSeries({{
      color: '#ab47bc', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
    }});
    rsiLine.setData({rsi_json});
    rsiSeries = rsiLine;
    const rsiOB = rsiChart.addLineSeries({{ color: 'rgba(239,83,80,0.4)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    rsiOB.setData({rsi_json}.length > 0 ? {rsi_json}.map(d => ({{ time: d.time, value: 70 }})) : []);
    const rsiOS = rsiChart.addLineSeries({{ color: 'rgba(38,166,154,0.4)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    rsiOS.setData({rsi_json}.length > 0 ? {rsi_json}.map(d => ({{ time: d.time, value: 30 }})) : []);
    const rsiMid = rsiChart.addLineSeries({{ color: 'rgba(139,152,169,0.3)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    rsiMid.setData({rsi_json}.length > 0 ? {rsi_json}.map(d => ({{ time: d.time, value: 50 }})) : []);
    rsiChart.timeScale().fitContent();

    /* MACD(12,26,9) */
    const macdEl = document.getElementById('macdchart');
    const macdChart = LightweightCharts.createChart(macdEl, {{
      ...cmn, width: macdEl.clientWidth, height: 160,
      rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.05 }} }},
    }});
    const macdHist = macdChart.addHistogramSeries({{ priceFormat: {{ type: 'price' }} }});
    macdHist.setData({macd_hist_json});
    macdHistSeries = macdHist;
    const macdLineS = macdChart.addLineSeries({{ color: '#5b8def', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false }});
    macdLineS.setData({macd_json});
    macdLineSeries = macdLineS;
    const macdSigS = macdChart.addLineSeries({{ color: '#ffa726', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }});
    macdSigS.setData({macd_signal_json});
    macdSignalSeries = macdSigS;
    const macdZeroData = {macd_json}.length > 0 ? [{{ time: {macd_json}[0].time, value: 0 }}, {{ time: {macd_json}[{macd_json}.length - 1].time, value: 0 }}] : [];
    macdChart.addLineSeries({{ color: '#4a5568', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData(macdZeroData);
    macdChart.timeScale().fitContent();

    /* Drawdown */
    const ddEl = document.getElementById('drawdown');
    const ddChart = LightweightCharts.createChart(ddEl, {{
      ...cmn, width: ddEl.clientWidth, height: 160,
      rightPriceScale: {{ scaleMargins: {{ top: 0.1, bottom: 0.05 }} }},
    }});
    const ddSeries = ddChart.addAreaSeries({{
      lineColor: '#ef5350', topColor: 'rgba(239,83,80,0.15)', bottomColor: 'rgba(239,83,80,0)',
      lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
    }});
    ddSeries.setData({drawdown_json});
    var ddZeroData = {drawdown_json}.length > 0 ? [{{ time: {drawdown_json}[0].time, value: 0 }}, {{ time: {drawdown_json}[{drawdown_json}.length - 1].time, value: 0 }}] : [];
    ddChart.addLineSeries({{ color: '#4a5568', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData(ddZeroData);
    const ddHs300 = ddChart.addLineSeries({{ color: '#5b8def', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    ddHs300.setData({dd_hs300_json});
    const ddSse = ddChart.addLineSeries({{ color: '#ffa726', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    ddSse.setData({dd_sse_json});
    ddChart.timeScale().fitContent();

    /* Daily P&L */
    const pEl = document.getElementById('pnlbar');
    const pChart = LightweightCharts.createChart(pEl, {{ ...cmn, width: pEl.clientWidth, height: 160 }});
    var pnlRaw = {pnl_bar_json};
    var pnlHistData = pnlRaw.map(function(d) {{
      return {{ time: d.time, value: d.value, color: d.color || (d.value >= 0 ? '#26a69a' : '#ef5350') }};
    }});
    pChart.addHistogramSeries({{ priceFormat: {{ type: 'volume' }} }}).setData(pnlHistData);
    var pZeroData = pnlRaw.length > 0 ? [{{ time: pnlRaw[0].time, value: 0 }}, {{ time: pnlRaw[pnlRaw.length - 1].time, value: 0 }}] : [];
    pChart.addLineSeries({{ color: '#4a5568', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData(pZeroData);
    pChart.timeScale().fitContent();

    /* Daily returns */
    const drEl = document.getElementById('dailyret');
    const drChart = LightweightCharts.createChart(drEl, {{ ...cmn, width: drEl.clientWidth, height: 160 }});
    var drRaw = {daily_returns_json};
    var drHistData = drRaw.map(function(d) {{
      return {{ time: d.time, value: d.value, color: d.color || (d.value >= 0 ? '#26a69a' : '#ef5350') }};
    }});
    drChart.addHistogramSeries({{ priceFormat: {{ type: 'percent' }} }}).setData(drHistData);
    var drZeroData = drRaw.length > 0 ? [{{ time: drRaw[0].time, value: 0 }}, {{ time: drRaw[drRaw.length - 1].time, value: 0 }}] : [];
    drChart.addLineSeries({{ color: '#4a5568', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData(drZeroData);
    drChart.timeScale().fitContent();

    /* Rolling metrics chart */
    var rollChart = null;
    window._resizeRolling = function() {{
      if (rollChart) rollChart.resize(rollEl.clientWidth, 260);
    }};
    var rollingSharpe = {rolling_sharpe_json};
    var rollingVol = {rolling_vol_json};
    if (rollingSharpe.length > 0 || rollingVol.length > 0) {{
      var rollEl = document.getElementById('rollingChart');
      rollChart = LightweightCharts.createChart(rollEl, {{ ...cmn, width: rollEl.clientWidth, height: 260 }});
      if (rollingSharpe.length > 0) {{
        var rsData = rollingSharpe.map(function(d) {{ return {{ time: d.date, value: d.value }}; }});
        var rsLine = rollChart.addLineSeries({{ color: '#5b8def', lineWidth: 2, title: 'Sharpe(60d)', priceLineVisible: false, lastValueVisible: true }});
        rsLine.setData(rsData);
      }}
      if (rollingVol.length > 0) {{
        var rvData = rollingVol.map(function(d) {{ return {{ time: d.date, value: d.value * 100 }}; }});
        var rvLine = rollChart.addLineSeries({{ color: '#ffa726', lineWidth: 1.5, lineStyle: 2, title: 'Vol%(60d)', priceLineVisible: false, lastValueVisible: true }});
        rvLine.setData(rvData);
      }}
      rollChart.timeScale().fitContent();
    }}

    /* Sync all time scales */
    const allCharts = [kChart, rChart, ddChart, pChart, drChart, rsiChart, macdChart];
    allCharts.forEach(src => {{
      src.timeScale().subscribeVisibleLogicalRangeChange(range => {{
        if (!range) return;
        allCharts.forEach(dst => {{ if (dst !== src) dst.timeScale().setVisibleLogicalRange(range); }});
      }});
    }});

    /* Responsive resize */
    let rTimer;
    window.addEventListener('resize', () => {{
      clearTimeout(rTimer);
      rTimer = setTimeout(() => {{
        [[kChart, kEl], [rChart, rEl], [ddChart, ddEl], [pChart, pEl], [drChart, drEl], [rsiChart, rsiEl], [macdChart, macdEl]]
          .forEach(([c, el]) => c.applyOptions({{ width: el.clientWidth }}));
      }}, 150);
    }});

    /* =================================================================
       INDICATOR TOGGLE
       ================================================================= */
    const indGroups = {{
      ma:   [ma5S, ma20S, ma60S],
      bb:   [bbUpperS, bbMiddleS, bbLowerS],
      vol:  [volS],
      sr:   [supS, resS],
    }};
    window.toggleInd = function(group, btn) {{
      const show = !btn.classList.contains('active');
      btn.classList.toggle('active');
      (indGroups[group] || []).forEach(s => s.applyOptions({{ visible: show }}));
    }};

    /* =================================================================
       CROSSHAIR LEGEND
       ================================================================= */
    const legendEl = document.getElementById('klineLegend');
    function buildMap(arr) {{
      const m = {{}};
      arr.forEach(d => {{ m[d.time] = d.value; }});
      return m;
    }}
    const ma5Map   = buildMap({ma5_json});
    const ma20Map  = buildMap({ma20_json});
    const ma60Map  = buildMap({ma60_json});
    const rsiMap   = buildMap({rsi_json});
    const macdMap  = buildMap({macd_json});
    const sigMap   = buildMap({macd_signal_json});
    const histMap  = buildMap({macd_hist_json});
    const bbUpMap  = buildMap({bb_upper_json});
    const bbMidMap = buildMap({bb_middle_json});
    const bbLoMap  = buildMap({bb_lower_json});
    const volMap   = buildMap({volume_json});

    function fmt(v, d) {{
      if (v === undefined || v === null || isNaN(v)) return '—';
      return Number(v).toFixed(d || 2);
    }}
    function fmtVol(v) {{
      if (v === undefined || v === null || isNaN(v)) return '—';
      const n = Number(v);
      if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
      if (n >= 1e4) return (n / 1e4).toFixed(2) + '万';
      return n.toLocaleString();
    }}

    kChart.subscribeCrosshairMove(param => {{
      if (!param || !param.time) {{
        legendEl.classList.remove('visible');
        return;
      }}
      legendEl.classList.add('visible');
      const t = param.time;
      const sd = param.seriesData.get(cSeries);
      const o = sd ? fmt(sd.open, 3) : '—';
      const h = sd ? fmt(sd.high, 3) : '—';
      const l = sd ? fmt(sd.low, 3) : '—';
      const c = sd ? fmt(sd.close, 3) : '—';

      let htm = '<div class="leg-date">' + t + '</div>';
      htm += '<div class="leg-row"><span class="leg-label">O/H/L/C</span><span class="leg-val">' + o + ' / ' + h + ' / ' + l + ' / ' + c + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#ef5350"></span>MA5</span><span class="leg-val">' + fmt(ma5Map[t]) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#5b8def"></span>MA20</span><span class="leg-val">' + fmt(ma20Map[t]) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#ab47bc"></span>MA60</span><span class="leg-val">' + fmt(ma60Map[t]) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#ab47bc"></span>RSI</span><span class="leg-val">' + fmt(rsiMap[t]) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#5b8def"></span>MACD</span><span class="leg-val">' + fmt(macdMap[t], 4) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#ffa726"></span>Signal</span><span class="leg-val">' + fmt(sigMap[t], 4) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label"><span class="leg-dot" style="background:#26a69a"></span>Hist</span><span class="leg-val">' + fmt(histMap[t], 4) + '</span></div>';
      htm += '<div class="leg-row"><span class="leg-label">VOL</span><span class="leg-val">' + fmtVol(volMap[t]) + '</span></div>';
      legendEl.innerHTML = htm;
    }});

  }} catch(e) {{
    chartError = true;
    console.error('Chart init error:', e);
    ['kline','returns','drawdown','pnlbar','dailyret','rsichart','macdchart','rollingChart'].forEach(function(id) {{
      var el = document.getElementById(id);
      if (el) {{
        el.style.display = 'flex'; el.style.alignItems = 'center'; el.style.justifyContent = 'center';
        el.style.color = '#4a5568'; el.style.fontSize = '14px';
        el.innerHTML = '<div style="text-align:center;padding:40px"><div style="font-size:24px;margin-bottom:8px">&#9888;</div>' +
          '<div>' + e.message + '</div><div style="font-size:12px;margin-top:8px;color:#4a5568">图表库加载失败</div></div>';
      }}
    }});
  }}

  /* Technical stats */
  const tech = {tech_json};
  if (Object.keys(tech).length > 0) {{
    document.getElementById('tech-section').style.display = '';
    const items = [
      ['最新价', tech.latest_price], ['MA5', tech.ma5], ['MA20', tech.ma20], ['MA60', tech.ma60],
      ['ATR(14)', tech.atr14], ['RSI(14)', tech.rsi14], ['MACD', tech.macd],
      ['Signal', tech.macd_signal], ['Hist', tech.macd_hist],
      ['BB Upper', tech.bb_upper], ['BB Middle', tech.bb_middle], ['BB Lower', tech.bb_lower],
      ['BB Width%', tech.bb_width], ['量比', tech.vol_ratio],
      ['期间最高', tech.period_high], ['期间最低', tech.period_low],
    ].filter(([, v]) => v !== null && v !== undefined);
    document.getElementById('tech-stats').innerHTML = items.map(([lbl, val]) =>
      '<div class="tech-card"><div class="title">' + lbl + '</div>' +
      '<div class="val">' + (typeof val === 'number' ? val.toLocaleString() : val) + '</div></div>'
    ).join('');
  }}

  /* Render grade badges */
  renderGrades();

  /* Tabs */
  document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
      const container = tab.closest('.tabbed-section') || tab.closest('.section') || tab.closest('.trade-section');
      if (!container) return;
      container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add('active');
      if (tab.dataset.tab === 'tb-dist' && window._drawDistribution) window._drawDistribution();
      if (tab.dataset.tab === 'tb-rolling' && window._resizeRolling) window._resizeRolling();
    }});
  }});

}})();
</script>
</body>
</html>"""




def generate_report_md(result, out_path):
    """Generate professional Markdown report with grade breakdown,
    monthly returns, rolling metrics, and top drawdown periods.
    """
    from eqlib.attribution import (
        analyze_returns, brinson_attribution, fama_french_analysis, grade_strategy,
    )
    from eqlib.data import fetch_stock_data

    ctx = result["context"]
    trade_log = result["trade_log"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)

    bench_data = {}
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_init = bench_df["close"].iloc[0]
            bench_final = bench_df["close"].iloc[-1]
            bench_data["return"] = (bench_final - bench_init) / bench_init * 100
    except Exception:
        pass

    bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    lines = []

    # ── Header ──────────────────────────────────────────────────────
    securities = list(set(t['security'] for t in trade_log) or ['N/A'])
    lines.append(f"# Backtest Report — {securities[0]}")
    lines.append("")
    lines.append(f"*Generated by {BRAND_NAME} · {ctx.start_date} to {ctx.end_date} · "
                 f"Grade: {grade_info['overall']} ({grade_info['score']}/100)*")
    lines.append("")

    # ── Strategy Summary ────────────────────────────────────────────
    lines.append("## Strategy Summary")
    lines.append("")
    lines.append(f"> {grade_info.get('summary_text', 'N/A')}")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **Period** | {ctx.start_date} to {ctx.end_date} |")
    lines.append(f"| **Initial Capital** | {initial:,.2f} |")
    lines.append(f"| **Final Value** | {final:,.2f} |")
    lines.append(f"| **P&L** | {pnl:+,.2f} ({pnl_pct:+.2f}%) |")
    lines.append(f"| **Benchmark** | {bench_label} |")
    if bench_data:
        lines.append(f"| **Benchmark Return** | {bench_data['return']:+.2f}% |")
    lines.append("")

    # ── Grade Breakdown ─────────────────────────────────────────────
    lines.append("## Grade Breakdown")
    lines.append("")
    lines.append("| Dimension | Score | Grade | Key Metric |")
    lines.append("|-----------|-------|-------|------------|")
    for d in grade_info.get("dimensions", []):
        key_str = ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                           for k, v in d.get("key", {}).items())
        lines.append(f"| {d['name']} | {d['score']:.0f} | {d.get('grade', 'N/A')} | {key_str} |")
    lines.append(f"| **Overall** | **{grade_info['score']:.0f}** | **{grade_info['overall']}** | |")
    lines.append("")

    # ── Performance Metrics ─────────────────────────────────────────
    if analytics:
        lines.append("## Performance Metrics")
        lines.append("")
        lines.append("| Metric | Value | Benchmark | Delta |")
        lines.append("|--------|-------|-----------|-------|")
        ann_ret = analytics["annual_return"]
        bench_ret_pct = bench_data.get("return", 0) / 100
        lines.append(f"| Annual Return | {ann_ret:+.2%} | {bench_ret_pct:+.2%} | {ann_ret - bench_ret_pct:+.2%} |")
        lines.append(f"| Annual Volatility | {analytics['annual_volatility']:.2%} | {analytics.get('benchmark_volatility', 0):.2%} | |")
        lines.append(f"| Sharpe Ratio | {analytics['sharpe_ratio']:.2f} | — | — |")
        lines.append(f"| Sortino Ratio | {analytics['sortino_ratio']:.2f} | — | — |")
        lines.append(f"| Max Drawdown | {analytics['max_drawdown']:.2%} | — | — |")
        lines.append(f"| Calmar Ratio | {analytics['calmar_ratio']:.2f} | — | — |")
        lines.append(f"| Alpha | {analytics['alpha']:+.2%} | — | — |")
        lines.append(f"| Beta | {analytics['beta']:.2f} | — | — |")
        lines.append(f"| Information Ratio | {analytics['information_ratio']:.2f} | — | — |")
        lines.append(f"| Win Rate (trade) | {analytics['win_rate_trade']:.1%} | — | — |")
        plr = analytics.get('profit_loss_ratio', 0)
        plr_str = '∞' if plr == float('inf') else f'{plr:.2f}'
        lines.append(f"| Profit/Loss Ratio | {plr_str} | — | — |")
        lines.append(f"| Trade Count | {analytics['trade_count']} | — | — |")
        lines.append("")

    # ── Monthly Returns ─────────────────────────────────────────────
    if analytics and analytics.get("monthly_returns"):
        lines.append("## Monthly Returns")
        lines.append("")
        mr = analytics["monthly_returns"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        lines.append("| Year | " + " | ".join(months) + " | YTD |")
        lines.append("|------|" + "|".join(["-----"] * 12) + "|-----|")
        years = sorted(set(k[:4] for k in mr.keys()))
        for year in years:
            row = [year]
            for m in range(1, 13):
                key = f"{year}-{m:02d}"
                val = mr.get(key)
                row.append(f"{val:+.1%}" if val is not None else "—")
            ytd_vals = [v for k, v in mr.items() if k.startswith(year)]
            ytd = 1.0
            for v in ytd_vals:
                ytd *= (1 + v)
            ytd -= 1
            row.append(f"{ytd:+.1%}")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # ── Rolling Metrics ─────────────────────────────────────────────
    if analytics and analytics.get("rolling_sharpe_60d"):
        lines.append("## Rolling Metrics (60-day window, quarterly sampled)")
        lines.append("")
        lines.append("| Date | Rolling Sharpe | Rolling Vol |")
        lines.append("|------|---------------|-------------|")
        rs = analytics["rolling_sharpe_60d"]
        rv = analytics["rolling_volatility_60d"]
        step = max(1, len(rs) // 4)
        for i in range(0, len(rs), step):
            date = rs[i]["date"]
            sharpe_val = rs[i]["value"]
            vol_val = rv[i]["value"] if i < len(rv) else 0
            lines.append(f"| {date} | {sharpe_val:.2f} | {vol_val:.1%} |")
        lines.append("")

    # ── Top 5 Drawdown Periods ──────────────────────────────────────
    if analytics and analytics.get("drawdown_periods"):
        lines.append("## Top 5 Drawdown Periods")
        lines.append("")
        lines.append("| # | Start | Trough | Recovery | Depth | Duration |")
        lines.append("|---|-------|--------|----------|-------|----------|")
        for dp in analytics["drawdown_periods"]:
            recovery = dp.get("recovery") or "ongoing"
            duration = f"{dp['duration_days']}d"
            lines.append(f"| {dp['rank']} | {dp['start']} | {dp['trough']} | "
                        f"{recovery} | {dp['depth']:.1%} | {duration} |")
        lines.append("")

    # ── Trade Analysis ──────────────────────────────────────────────
    lines.append("## Trade Analysis")
    lines.append("")
    buy_count = sum(1 for t in trade_log if t["type"] == "BUY")
    sell_count = sum(1 for t in trade_log if t["type"] == "SELL")
    total_commission = sum(t.get("commission", 0) for t in trade_log)
    lines.append(f"- Buy orders: {buy_count}")
    lines.append(f"- Sell orders: {sell_count}")
    lines.append(f"- Total commission: {total_commission:,.2f}")
    lines.append(f"- Securities traded: {len(set(t['security'] for t in trade_log))}")
    lines.append("")

    if analytics and analytics.get("per_stock_pnl"):
        lines.append("### Per-Stock P&L")
        lines.append("")
        lines.append("| Security | P&L |")
        lines.append("|----------|-----|")
        for sec, pnl_val in sorted(analytics["per_stock_pnl"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {sec} | {pnl_val:+,.2f} |")
        lines.append("")

    # ── Trade P&L ───────────────────────────────────────────────────
    if trade_log:
        lines.append("## Trade P&L")
        lines.append("")
        lines.append("| # | Security | Buy Date | Buy Price | Sell Date | Sell Price | P&L |")
        lines.append("|---|----------|----------|-----------|-----------|------------|-----|")
        trade_pairs = {}
        trade_num = 0
        for t in trade_log:
            sec = t["security"]
            if sec not in trade_pairs:
                trade_pairs[sec] = []
            if t["type"] == "BUY":
                trade_pairs[sec].append(t)
            elif t["type"] == "SELL" and trade_pairs[sec]:
                buy_t = trade_pairs[sec].pop(0)
                buy_val = buy_t["price"] * buy_t["amount"] + buy_t.get("commission", 0)
                sell_val = t["price"] * t["amount"] - t.get("commission", 0)
                trade_pnl = sell_val - buy_val
                trade_num += 1
                lines.append(
                    f"| {trade_num} | {sec} | {buy_t['date']} | {buy_t['price']:.3f} "
                    f"| {t['date']} | {t['price']:.3f} | {trade_pnl:+,.0f} |"
                )
        lines.append("")

    # ── Factor Analysis ─────────────────────────────────────────────
    ff = fama_french_analysis(result)
    if ff:
        lines.append("## Factor Analysis")
        lines.append("")
        lines.append("| Factor | Value |")
        lines.append("|--------|-------|")
        for k, v in ff.items():
            if isinstance(v, float):
                lines.append(f"| {k} | {v:.4f} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")

    # ── Brinson Attribution ─────────────────────────────────────────
    br = brinson_attribution(result)
    if br:
        lines.append("## Brinson Attribution")
        lines.append("")
        lines.append("| Component | Effect |")
        lines.append("|-----------|--------|")
        for k, v in br.items():
            if isinstance(v, float):
                lines.append(f"| {k} | {v:+.2%} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")

    # ── Data Sources ────────────────────────────────────────────────
    lines.append("## Data Sources")
    lines.append("")
    lines.append("| Source | Details |")
    lines.append("|--------|---------|")
    lines.append("| Market Data | AKShare `stock_zh_a_hist` (EastMoney), forward-adjusted daily OHLCV |")
    lines.append("| Benchmark | CSI 300 / SSE Composite via AKShare `stock_zh_index_daily_em` |")
    lines.append("| Risk-Free Rate | 3.0% per annum, daily = 3% / 252 |")
    lines.append("| Backtest Engine | EasyQuant eqlib — event-driven, T+1 |")
    lines.append("")
    lines.append("> **Disclaimer:** This report is generated by EasyQuant for research purposes only and")
    lines.append("> does not constitute investment advice. Past performance is not indicative of future results.")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report saved: {out_path}")


def generate_report_json(result, out_path, *,
                         strategy_params=None,
                         iteration_context=None):
    """Generate Agent-First JSON report with verdict/targets/diagnostics/recommendations.

    Args:
        result: dict from run_backtest()
        out_path: output file path
        strategy_params: {"current": {...}, "ranges": {...}} or None
        iteration_context: {"run_id": "...", "previous_run_id": "...",
                            "changes_applied": {...}, "previous_metrics": {...}} or None
    """
    from eqlib.attribution import (
        analyze_returns, brinson_attribution, fama_french_analysis,
        grade_strategy, diagnose_bottleneck, recommend_params,
    )

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)

    # Benchmark data
    bench_return = None
    try:
        from eqlib.data import fetch_stock_data
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_return = float(bench_df["close"].iloc[-1] / bench_df["close"].iloc[0] - 1)
    except Exception:
        pass

    # Cumulative return series
    pf_entries = sorted(
        recorded.values(), key=lambda x: x.get("date", datetime.date.min)
    ) if isinstance(recorded, dict) else recorded
    cumulative_returns = []
    for r in pf_entries:
        if "total_value" in r:
            cumulative_returns.append({
                "date": str(r["date"]),
                "total_value": round(r["total_value"], 2),
                "cumulative_return": round(r["total_value"] / initial - 1, 6) if initial > 0 else 0.0,
            })

    # Chart data for native rendering
    chart = _compute_chart_data(result)

    # ── Layer 1: verdict ────────────────────────────────────────────
    targets_def = {
        "sharpe_ratio": {"op": ">=", "threshold": 1.0},
        "max_drawdown": {"op": ">=", "threshold": -0.20},
        "annual_return": {"op": ">=", "threshold": 0.0},
        "win_rate_trade": {"op": ">=", "threshold": 0.40},
        "alpha": {"op": ">=", "threshold": 0.0},
        "beta": {"op": "between", "threshold": [0.3, 1.3]},
        "trade_count": {"op": ">=", "threshold": 3},
    }

    # ── Layer 2: targets ────────────────────────────────────────────
    targets = []
    all_pass = True
    priority_counter = 0
    for metric_name, target_def in targets_def.items():
        value = analytics.get(metric_name, 0) if analytics else 0
        op = target_def["op"]
        threshold = target_def["threshold"]
        if op == ">=":
            passed = value >= threshold
            gap = f"{value - threshold:+.4f}" if isinstance(value, (int, float)) else str(value)
        elif op == "between":
            lo, hi = threshold
            passed = lo <= value <= hi
            gap = "in range" if passed else f"out of [{lo}, {hi}]"
        else:
            passed = True
            gap = "N/A"

        if not passed:
            all_pass = False
            priority_counter += 1
            targets.append({
                "metric": metric_name, "value": value,
                "target": target_def, "pass": False,
                "gap": gap, "priority": priority_counter,
            })
        else:
            targets.append({
                "metric": metric_name, "value": value,
                "target": target_def, "pass": True,
                "gap": gap, "priority": None,
            })

    # Sort: failing first by priority, then passing
    targets.sort(key=lambda t: (t["pass"], t.get("priority") or 999))

    bottleneck = grade_info.get("weakest", "") if not all_pass else None
    action = "complete" if all_pass else "adjust_params"
    verdict = {
        "pass": all_pass,
        "grade": grade_info["overall"],
        "score": grade_info["score"],
        "bottleneck": bottleneck,
        "action": action,
        "summary": grade_info.get("summary_text", ""),
    }

    # ── Layer 3: diagnostics ────────────────────────────────────────
    diagnostics = diagnose_bottleneck(analytics, grade_info) if analytics else []

    # ── Layer 4: recommendations ────────────────────────────────────
    current_p = strategy_params.get("current", {}) if strategy_params else None
    ranges_p = strategy_params.get("ranges", {}) if strategy_params else None
    recommendations = recommend_params(analytics, grade_info, current_p, ranges_p)

    # ── Layer 6: iteration ──────────────────────────────────────────
    iteration = None
    if iteration_context:
        prev_metrics = iteration_context.get("previous_metrics", {})
        metric_deltas = {}
        for key in ["annual_return", "sharpe_ratio", "max_drawdown",
                     "annual_volatility", "win_rate_trade"]:
            cur_val = analytics.get(key, 0) if analytics else 0
            prev_val = prev_metrics.get(key, None)
            if prev_val is not None:
                delta = cur_val - prev_val
                improved = (delta > 0) if key != "max_drawdown" else (delta > 0)
                if key == "annual_volatility":
                    improved = delta < 0
                metric_deltas[key] = {
                    "from": prev_val, "to": cur_val,
                    "delta": f"{delta:+.4f}", "improved": improved,
                }
        prev_score = prev_metrics.get("_grade_score", 0)
        score_delta = grade_info["score"] - prev_score
        regression = any(
            not v["improved"] for k, v in metric_deltas.items()
            if k in ("annual_return", "sharpe_ratio", "max_drawdown")
        )
        iteration = {
            "run_id": iteration_context.get("run_id", ""),
            "previous_run_id": iteration_context.get("previous_run_id", ""),
            "changes_applied": iteration_context.get("changes_applied", {}),
            "score_delta": score_delta,
            "previous_grade": prev_metrics.get("_grade", ""),
            "metric_deltas": metric_deltas,
            "regression_detected": regression,
            "convergence_note": "",
        }

    # ── Build final report ──────────────────────────────────────────
    report = {
        "verdict": verdict,
        "targets": targets,
        "diagnostics": diagnostics,
        "recommendations": recommendations,
    }

    if strategy_params:
        report["strategy_params"] = strategy_params

    if iteration:
        report["iteration"] = iteration

    report["grade"] = grade_info

    # Raw metrics — filter inf/nan for valid JSON output
    def _safe_val(v):
        if isinstance(v, float):
            return round(v, 6) if np.isfinite(v) else None
        return v

    if analytics:
        report["metrics"] = {
            k: _safe_val(v)
            for k, v in analytics.items()
            if isinstance(v, (int, float, str, bool))
        }
        report["time_series"] = {
            "monthly_returns": analytics.get("monthly_returns", {}),
            "rolling_sharpe_60d": analytics.get("rolling_sharpe_60d", []),
            "rolling_volatility_60d": analytics.get("rolling_volatility_60d", []),
            "drawdown_periods": analytics.get("drawdown_periods", []),
        }
        report["daily_returns_stats"] = analytics.get("daily_returns_stats", {})
        report["per_stock_pnl"] = {
            k: round(v, 2) for k, v in analytics.get("per_stock_pnl", {}).items()
        }
    else:
        report["metrics"] = None
        report["time_series"] = {}
        report["daily_returns_stats"] = {}
        report["per_stock_pnl"] = {}

    report["summary"] = {
        "start_date": str(ctx.start_date),
        "end_date": str(ctx.end_date),
        "initial_capital": initial,
        "final_value": round(final, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "num_trades": len(trade_log),
        "securities": list(set(t["security"] for t in trade_log) or []),
        "benchmark": benchmark,
        "benchmark_return": round(bench_return, 4) if bench_return is not None else None,
    }

    report["trades"] = [
        {
            "type": t["type"], "date": str(t["date"]),
            "security": t["security"], "price": t["price"],
            "amount": t["amount"], "commission": round(t.get("commission", 0), 2),
        }
        for t in trade_log
    ]

    report["positions"] = {
        sec: {
            "amount": pos.amount,
            "avg_cost": round(pos.avg_cost, 3),
            "total_value": round(pos.total_value, 2),
        }
        for sec, pos in ctx.portfolio.positions.items()
        if pos.amount > 0
    }

    # Chart data
    report["chart_data"] = {
        "candlestick_data": chart["candlestick_data"],
        "volume_data": chart["volume_data"],
        "cum_return_data": chart["cum_return_data"],
        "drawdown_data": chart["drawdown_data"],
    }

    # Factor analysis — filter inf/nan for valid JSON output
    ff = fama_french_analysis(result)
    if ff:
        report["factor_analysis"] = {
            k: (round(v, 4) if isinstance(v, float) and np.isfinite(v) else
                None if isinstance(v, float) else v)
            for k, v in ff.items()
        }

    br = brinson_attribution(result)
    if br:
        report["brinson_attribution"] = {
            k: (round(v, 4) if isinstance(v, float) and np.isfinite(v) else
                None if isinstance(v, float) else v)
            for k, v in br.items()
        }

    # ── Backward-compatible keys for existing callers ─────────────────
    # runs.py, ReportViewer.tsx, and examples/05_reports.py depend on
    # the old top-level keys (risk_metrics, cumulative_returns).
    if analytics:
        pl_ratio = analytics.get("profit_loss_ratio", 0)
        report["risk_metrics"] = {
            "total_return": _safe_val(analytics.get("total_return", 0)),
            "annual_return": _safe_val(analytics.get("annual_return", 0)),
            "annual_volatility": _safe_val(analytics.get("annual_volatility", 0)),
            "sharpe_ratio": _safe_val(analytics.get("sharpe_ratio", 0)),
            "sortino_ratio": _safe_val(analytics.get("sortino_ratio", 0)),
            "max_drawdown": _safe_val(analytics.get("max_drawdown", 0)),
            "calmar_ratio": _safe_val(analytics.get("calmar_ratio", 0)),
            "alpha": _safe_val(analytics.get("alpha", 0)),
            "beta": _safe_val(analytics.get("beta", 0)),
            "win_rate_trade": _safe_val(analytics.get("win_rate_trade", 0)),
            "win_rate_daily": _safe_val(analytics.get("win_rate_daily", 0)),
            "profit_loss_ratio": None if not np.isfinite(pl_ratio) else round(pl_ratio, 2),
            "trade_count": analytics.get("trade_count", 0),
            "information_ratio": _safe_val(analytics.get("information_ratio", 0)),
            "excess_return": _safe_val(analytics.get("excess_return", 0)),
            "benchmark_return": _safe_val(analytics.get("benchmark_return", 0)),
        }

    report["cumulative_returns"] = cumulative_returns

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Data saved: {out_path}")
