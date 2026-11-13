"""Report generation: chart (PNG), HTML (self-contained SVG, no CDN), JSON, and Markdown."""

import os
import json
import html
import math
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["font.sans-serif"] = ["PingFang HK", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

from eqlib.data import fetch_stock_data, get_price
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
from eqlib.reporting.diagnostics import collect_data_diagnostics
from eqlib.brand import (
    BRAND_NAME,
    apply_matplotlib_brand,
    html_footer_brand_chip,
    html_header_brand_lockup,
)
import pandas as pd
import numpy as np


def _sanitize_json_value(value):
    """Recursively replace non-finite numeric values with JSON null."""
    if isinstance(value, dict):
        return {
            key: _sanitize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


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


_CHART_OHLC_COLUMNS = ("open", "high", "low", "close")


def _clean_chart_ohlcv(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Return sorted OHLCV rows that are safe to serialize into chart JSON."""
    if df is None or df.empty:
        return pd.DataFrame()
    if not set(_CHART_OHLC_COLUMNS).issubset(df.columns):
        return pd.DataFrame()

    df_sorted = df.sort_index().copy()
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    try:
        ranged = df_sorted.loc[start_ts:end_ts]
        if not ranged.empty:
            df_sorted = ranged
    except Exception:
        pass

    numeric_cols = list(_CHART_OHLC_COLUMNS)
    if "volume" in df_sorted.columns:
        numeric_cols.append("volume")
    for col in numeric_cols:
        df_sorted[col] = pd.to_numeric(df_sorted[col], errors="coerce")

    df_sorted = df_sorted.dropna(subset=list(_CHART_OHLC_COLUMNS))
    if df_sorted.empty:
        return pd.DataFrame()

    finite_mask = np.isfinite(df_sorted[list(_CHART_OHLC_COLUMNS)]).all(axis=1)
    positive_mask = (df_sorted[list(_CHART_OHLC_COLUMNS)] > 0).all(axis=1)
    df_sorted = df_sorted[finite_mask & positive_mask]
    if df_sorted.empty:
        return pd.DataFrame()

    if "volume" not in df_sorted.columns:
        df_sorted["volume"] = 0.0
    else:
        df_sorted["volume"] = df_sorted["volume"].fillna(0.0)
    return df_sorted


def _better_chart_coverage(candidate: pd.DataFrame, current: pd.DataFrame) -> bool:
    """Whether candidate provides better chart coverage than current."""
    if candidate.empty:
        return False
    if current.empty:
        return True
    candidate_start = pd.Timestamp(candidate.index.min())
    current_start = pd.Timestamp(current.index.min())
    if candidate_start < current_start:
        return True
    if candidate_start == current_start and len(candidate) > len(current):
        return True
    return len(candidate) > len(current) * 1.25


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
    # Anchor to starting cash so the chart endpoint equals the reported
    # total return exactly; fall back to the first recorded value only when
    # starting cash is missing/invalid.
    init_val = initial if (initial and initial > 0) else by_date[sorted_dates[0]]
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

    Divide the decline by peak wealth (100 + peak cumulative return),
    including initial wealth of 100 before the first observation.
    """
    if not cum_points:
        return []
    out = []
    peak = 0.0
    for d in cum_points:
        v = d["value"]
        if v > peak:
            peak = v
        drawdown_pct = (v - peak) / (100.0 + peak) * 100.0
        out.append({"time": d["time"], "value": round(drawdown_pct, 3)})
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


def _benchmark_returns_from_result(result, recorded):
    """Build aligned cumulative benchmark returns from engine output."""
    raw_values = result.get("benchmark_values")
    if not isinstance(raw_values, list) or not raw_values:
        return []

    entries = (
        sorted(
            recorded.values(),
            key=lambda item: item.get("date", datetime.date.min),
        )
        if isinstance(recorded, dict)
        else recorded
    )
    target_times = [
        _to_tv_date(item["date"])
        for item in entries
        if isinstance(item, dict)
        and item.get("date") is not None
        and "total_value" in item
    ]
    if not target_times:
        return []

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
    if not rows:
        return []

    frame = pd.DataFrame(
        {"close": [value for _date, value in rows]},
        index=pd.DatetimeIndex([date for date, _value in rows]),
    )
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return _align_index_close_to_times(target_times, frame)


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

    source_df = ohlcv_data.get(symbol, pd.DataFrame())
    df_sorted = _clean_chart_ohlcv(source_df, start, end)
    needs_fetch = df_sorted.empty
    if not df_sorted.empty:
        start_ts = pd.Timestamp(start)
        needs_fetch = pd.Timestamp(df_sorted.index.min()) > start_ts + pd.Timedelta(days=30)

    if needs_fetch:
        try:
            fetched = _clean_chart_ohlcv(fetch_stock_data(symbol, start, end), start, end)
            if _better_chart_coverage(fetched, df_sorted):
                df_sorted = fetched
        except Exception:
            pass

    if not df_sorted.empty:
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

    # RSI(14), MACD(12,26,9), Bollinger Bands(20,2)
    rsi_data, macd_data, macd_signal_data, macd_hist_data = [], [], [], []
    bb_upper_data, bb_middle_data, bb_lower_data = [], [], []

    if not df_sorted.empty and len(df_sorted) >= 26:
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

    # Buy/sell markers for this symbol only (skip non-trade events such as
    # ORDER_TIMEOUT / DELIST_LIQUIDATE, which carry no price/amount)
    markers = []
    for t in trade_log:
        if t.get("security") == symbol and t.get("type") in ("BUY", "SELL"):
            markers.append({
                "time": _to_tv_date(t["date"]),
                "position": "belowBar" if t["type"] == "BUY" else "aboveBar",
                "color": "#26a69a" if t["type"] == "BUY" else "#ef5350",
                "shape": "arrowUp" if t["type"] == "BUY" else "arrowDown",
                "text": f"{'买' if t['type'] == 'BUY' else '卖'} {t.get('amount', 0)}",
            })
    markers.sort(key=lambda x: x["time"])

    # Technical summary stats
    tech_stats = {}
    if not df_sorted.empty:
        df_s = df_sorted.sort_index()
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

    ohlcv_data = result.get("ohlcv_data", {})

    # Compute K-line data for ALL traded securities
    symbols_data = {}
    for sym in symbols_list:
        symbols_data[sym] = _compute_symbol_kline(sym, start, end, ohlcv_data, trade_log)

    def _primary_symbol_rank(sym):
        candles = symbols_data[sym].get("candlestick_data", [])
        if not candles:
            return (0, pd.Timestamp.max, sym)
        return (len(candles), pd.Timestamp(candles[0]["time"]), sym)

    # Primary symbol data: prefer the traded stock with the broadest visible
    # chart history so long backtest reports do not open on a truncated series.
    symbol = sorted(
        symbols_list,
        key=lambda sym: (-_primary_symbol_rank(sym)[0],
                         _primary_symbol_rank(sym)[1],
                         _primary_symbol_rank(sym)[2]),
    )[0]
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
    drawdown_data = _build_drawdown_from_cumulative_pct(cum_return_data)

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


# ============================================================
# HTML report — self-contained terminal design (no CDN, no external requests)
#
# Architecture: this module computes every number and embeds them as a single
# JSON payload; eqlib/static/report.{html,css,js} provide the shell, design
# system, and a hand-rolled SVG chart engine that renders geometry only.
# ============================================================

_GRADE_COLORS = {"S": "#26a69a", "A": "#3987e5", "B": "#c99700", "C": "#d95926", "D": "#ef5350"}

_DIM_NAMES = {
    "return_capability": "收益能力",
    "risk_control": "风险控制",
    "risk_adjusted": "风险调整",
    "trade_quality": "交易质量",
    "excess_capability": "超额能力",
    "stability": "稳定性",
}


def _load_report_asset(name):
    """Read a bundled static asset (report.html / report.css / report.js)."""
    from importlib.resources import files
    return files("eqlib").joinpath("static", name).read_text(encoding="utf-8")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


def _pct_cls(v):
    """CSS class for a signed value (up/down/empty)."""
    if not _is_num(v):
        return ""
    return "up" if v >= 0 else "down"


def _fmt_pct_frac(v, dp=2, sign=False):
    """Format a fraction (0.0123) as a percent string."""
    if not _is_num(v):
        return "N/A"
    s = f"{v * 100:.{dp}f}%"
    return f"+{s}" if sign and v >= 0 else s


def _fmt_money(v):
    if not _is_num(v):
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e8:
        return f"{sign}{a / 1e8:.2f} 亿"
    if a >= 1e4:
        return f"{sign}{a / 1e4:.2f} 万"
    return f"{sign}{a:,.0f}"


def _json_for_script(payload):
    """Serialize payload for embedding inside a <script type=application/json> tag."""
    text = json.dumps(
        _sanitize_json_value(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    # Prevent </script> breakout from any string value
    return text.replace("</", "<\\/")


def _align_series_to_dates(points, idx_of, n):
    """Align [{time, value}] points onto the master date axis (None for gaps)."""
    out = [None] * n
    for p in points or []:
        i = idx_of.get(p.get("time"))
        if i is not None and _is_num(p.get("value")):
            out[i] = p["value"]
    return out


def _annual_return_rows(dates, strat_pct, bench_pct):
    """Per-calendar-year returns derived from cumulative-% series (compounded)."""
    years = {}
    for i, d in enumerate(dates):
        years.setdefault(d[:4], []).append(i)
    rows = []
    for y in sorted(years):
        idxs = years[y]
        first, last = idxs[0], idxs[-1]
        if not _is_num(strat_pct[last]):
            continue
        s_start = strat_pct[first - 1] if first > 0 and _is_num(strat_pct[first - 1]) else 0.0
        s_ret = (1 + strat_pct[last] / 100) / (1 + s_start / 100) - 1
        b_ret = None
        if _is_num(bench_pct[last]):
            b_start = bench_pct[first - 1] if first > 0 and _is_num(bench_pct[first - 1]) else 0.0
            b_ret = (1 + bench_pct[last] / 100) / (1 + b_start / 100) - 1
        rows.append({
            "year": y,
            "strategy": round(s_ret, 6),
            "benchmark": round(b_ret, 6) if b_ret is not None else None,
            "excess": round(s_ret - b_ret, 6) if b_ret is not None else None,
        })
    return rows


def _distribution_bins(daily_rets, max_bins=48):
    """Adaptive histogram covering the true [min, max] range (tails included)."""
    if not daily_rets:
        return []
    lo, hi = min(daily_rets), max(daily_rets)
    lo = min(lo, 0.0)
    hi = max(hi, 0.0)
    if hi - lo < 1e-9:
        hi = lo + 0.001
    width = None
    for w in (0.001, 0.002, 0.0025, 0.005, 0.01, 0.02):
        if (hi - lo) / w <= max_bins:
            width = w
            break
    if width is None:
        width = (hi - lo) / max_bins
    x0 = math.floor(lo / width) * width
    x1 = math.ceil(hi / width) * width
    n = max(1, int(round((x1 - x0) / width)))
    counts = [0] * n
    for r in daily_rets:
        i = int((r - x0) / width)
        counts[min(n - 1, max(0, i))] += 1
    return [{"x0": round(x0 + i * width, 4), "x1": round(x0 + (i + 1) * width, 4), "count": counts[i]}
            for i in range(n)]


def _kline_payload(symbol, sym_data, trade_log):
    """Columnar K-line payload for one symbol (arrays aligned to its dates)."""
    candles = sym_data.get("candlestick_data") or []
    if not candles:
        return None
    dates = [c["time"] for c in candles]
    idx_of = {d: i for i, d in enumerate(dates)}

    def col(key):
        m = {p["time"]: p["value"] for p in sym_data.get(key) or []}
        return [m.get(d) for d in dates]

    vol_map = {p["time"]: p["value"] for p in sym_data.get("volume_data") or []}

    # Limit-up flags (A-share): board-based daily limit, close near session high.
    # Approximation: 30% BSE (8xx/4xx/920), 20% ChiNext/STAR (300/301/688),
    # else 10% main board. Flagged when close/prev_close clears the threshold.
    closes = [c["close"] for c in candles]
    sym_s = str(symbol)
    if sym_s.startswith(("300", "301", "688")):
        lim_thr = 0.198
    elif sym_s.startswith(("8", "4", "920")):
        lim_thr = 0.298
    else:
        lim_thr = 0.098
    lim = [False] * len(candles)
    for i in range(1, len(candles)):
        prev = closes[i - 1]
        if prev > 0 and closes[i] / prev - 1 >= lim_thr - 0.002:
            lim[i] = True

    markers = []
    for t in trade_log:
        if t.get("type") not in ("BUY", "SELL"):
            continue
        d = _to_tv_date(t.get("date"))
        i = idx_of.get(d)
        if i is None:
            continue
        action = "买入" if t["type"] == "BUY" else "卖出"
        price = t.get("price")
        price_txt = f" @ {price:.2f}" if _is_num(price) else ""
        markers.append({
            "i": i,
            "dir": "B" if t["type"] == "BUY" else "S",
            "text": f"{action} {t.get('amount', 0):,} 股{price_txt}",
        })
    return {
        "dates": dates,
        "o": [c["open"] for c in candles],
        "h": [c["high"] for c in candles],
        "l": [c["low"] for c in candles],
        "c": [c["close"] for c in candles],
        "v": [vol_map.get(d) for d in dates],
        "lim": lim,
        "ma5": col("ma5_data"),
        "ma20": col("ma20_data"),
        "ma60": col("ma60_data"),
        "bb_u": col("bb_upper_data"),
        "bb_m": col("bb_middle_data"),
        "bb_l": col("bb_lower_data"),
        "sup": col("support_data"),
        "res": col("resistance_data"),
        "rsi": col("rsi_data"),
        "macd_dif": col("macd_data"),
        "macd_dea": col("macd_signal_data"),
        "macd_hist": col("macd_hist_data"),
        "markers": markers,
        "tech": sym_data.get("tech_stats") or {},
    }


def _build_report_payload(result, chart, metrics, bench_data):
    """Assemble the JSON payload embedded in the HTML report.

    Every number shown by the JavaScript layer is computed here in Python
    (single source of truth); the browser only renders geometry.
    """
    ctx = result["context"]
    recorded = result.get("recorded_values") or []
    trade_log = result.get("trade_log") or []
    analytics = metrics.get("_raw_analytics") or {}
    grade_data = metrics.get("grade_data") or {}

    cum = chart.get("cum_return_data") or []
    dates = [p["time"] for p in cum]
    n = len(dates)
    idx_of = {d: i for i, d in enumerate(dates)}

    strategy_pct = [p["value"] if _is_num(p.get("value")) else None for p in cum]
    bench_pct = _align_series_to_dates(bench_data, idx_of, n)
    hs300_pct = _align_series_to_dates(chart.get("ret_hs300_data"), idx_of, n)
    sse_pct = _align_series_to_dates(chart.get("ret_sse_data"), idx_of, n)
    dd_strat = _align_series_to_dates(chart.get("drawdown_data"), idx_of, n)
    dd_bench = (
        _align_series_to_dates(_build_drawdown_from_cumulative_pct(bench_data), idx_of, n)
        if bench_data else [None] * n
    )
    excess = [
        round(s - b, 4) if (_is_num(s) and _is_num(b)) else None
        for s, b in zip(strategy_pct, bench_pct)
    ]

    # Allocation: cash vs invested (from daily recorded snapshots)
    cash_arr = [None] * n
    inv_arr = [None] * n
    entries = recorded.values() if isinstance(recorded, dict) else recorded
    for r in entries:
        if not isinstance(r, dict):
            continue
        i = idx_of.get(_to_tv_date(r.get("date")))
        if i is None:
            continue
        tv, cash = r.get("total_value"), r.get("cash")
        if _is_num(cash):
            cash_arr[i] = round(float(cash), 2)
        if _is_num(tv) and _is_num(cash):
            inv_arr[i] = round(max(0.0, float(tv) - float(cash)), 2)

    # Daily returns (fractions) — same source values as analyze_returns
    daily_rets = []
    prev_w = None
    for v in strategy_pct:
        if not _is_num(v):
            continue
        w = 1 + v / 100
        if prev_w is not None and prev_w > 0:
            daily_rets.append(w / prev_w - 1)
        prev_w = w

    # Benchmark identity
    benchmark = result.get("benchmark", "000300.XSHG")
    bench_code = str(benchmark).replace(".XSHG", "").replace(".XSHE", "")
    bench_label = {"000300": "沪深300", "000001": "上证指数", "000905": "中证500",
                   "000016": "上证50", "399006": "创业板指"}.get(bench_code, bench_code)

    # Trade quality extras (FIFO round trips, fees already netted in pnl)
    avg_win = avg_loss = None
    try:
        from eqlib.attribution import _match_round_trips
        clean_trades = [t for t in trade_log if t.get("type") in ("BUY", "SELL")
                        and _is_num(t.get("price")) and _is_num(t.get("amount"))]
        trips = _match_round_trips(clean_trades)
        wins = [t["pnl"] for t in trips if t.get("pnl", 0) > 0]
        losses = [t["pnl"] for t in trips if t.get("pnl", 0) < 0]
        if wins:
            avg_win = round(sum(wins) / len(wins), 2)
        if losses:
            avg_loss = round(sum(losses) / len(losses), 2)
    except Exception:
        pass

    # Non-trade events (audit trail): ORDER_TIMEOUT / DELIST_LIQUIDATE / ...
    trade_events = []
    for t in trade_log:
        if t.get("type") in ("BUY", "SELL"):
            continue
        label = {"ORDER_TIMEOUT": "超时撤单", "DELIST_LIQUIDATE": "退市清算"}.get(
            t.get("type"), str(t.get("type")))
        note = t.get("reason") or t.get("action") or ""
        trade_events.append({
            "date": _to_tv_date(t.get("date")),
            "security": str(t.get("security", "")),
            "label": label,
            "note": str(note),
        })

    # Diagnostics (bottleneck findings)
    diagnostics = []
    if analytics:
        try:
            from eqlib.attribution import diagnose_bottleneck
            diagnostics = diagnose_bottleneck(analytics, grade_data) or []
        except Exception:
            diagnostics = []

    kline = {}
    for sym, sym_data in (chart.get("symbols_data") or {}).items():
        kp = _kline_payload(symbol=sym, sym_data=sym_data, trade_log=trade_log)
        if kp:
            kline[sym] = kp

    # Localize dimension names embedded in the grade summary sentence
    summary_text = grade_data.get("summary_text", "") or ""
    for en_name, zh_name in _DIM_NAMES.items():
        summary_text = summary_text.replace(en_name, zh_name)

    per_stock = [
        {"sec": sec, "pnl": round(float(v), 2)}
        for sec, v in sorted((analytics.get("per_stock_pnl") or {}).items(),
                             key=lambda kv: abs(kv[1]), reverse=True)
        if _is_num(v)
    ]

    return {
        "meta": {
            "symbol": (chart.get("symbol") or "").replace(".XSHG", "").replace(".XSHE", ""),
            "symbols": chart.get("symbols_list") or [],
            "start": str(ctx.start_date),
            "end": str(ctx.end_date),
            "initial": ctx.portfolio.starting_cash,
            "final": ctx.portfolio.total_value,
            "trading_days": analytics.get("trading_days"),
            "benchmark_code": bench_code,
            "benchmark_label": bench_label,
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "dates": dates,
        "equity": {
            "strategy": strategy_pct,
            "benchmark": bench_pct if any(v is not None for v in bench_pct) else None,
            "hs300": hs300_pct if any(v is not None for v in hs300_pct) else None,
            "sse": sse_pct if any(v is not None for v in sse_pct) else None,
        },
        "drawdown": {"strategy": dd_strat, "benchmark": dd_bench},
        "drawdown_periods": analytics.get("drawdown_periods") or [],
        "excess": excess if any(v is not None for v in excess) else None,
        "allocation": {"cash": cash_arr, "invested": inv_arr},
        "monthly": analytics.get("monthly_returns") or {},
        "annual": _annual_return_rows(dates, strategy_pct, bench_pct),
        "dist": {
            "bins": _distribution_bins(daily_rets),
            "stats": analytics.get("daily_returns_stats") or {},
        },
        "rolling": {
            "sharpe": [{"t": p["date"], "v": p["value"]} for p in analytics.get("rolling_sharpe_60d") or []],
            "vol": [{"t": p["date"], "v": p["value"]} for p in analytics.get("rolling_volatility_60d") or []],
        },
        "kline": kline,
        "trade_marks": [
            {"i": idx_of[_to_tv_date(t["date"])],
             "dir": "B" if t["type"] == "BUY" else "S"}
            for t in trade_log
            if t.get("type") in ("BUY", "SELL") and _to_tv_date(t.get("date")) in idx_of
        ],
        "per_stock_pnl": per_stock,
        "grade": {
            "overall": grade_data.get("overall", "N/A"),
            "score": grade_data.get("score", 0),
            "dimensions": [
                {"name": d.get("name", ""), "label": _DIM_NAMES.get(d.get("name"), d.get("name", "")),
                 "score": d.get("score", 0)}
                for d in grade_data.get("dimensions") or []
            ],
            "weakest": grade_data.get("weakest", ""),
            "strongest": grade_data.get("strongest", ""),
            "summary_text": summary_text,
        },
        "diagnostics": [
            {"metric": d.get("metric", ""), "severity": d.get("severity", ""),
             "finding": str(d.get("finding", "")), "root_cause": str(d.get("root_cause", ""))}
            for d in diagnostics
        ],
        "trade_stats": {
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_commission": analytics.get("total_commission"),
            "annual_turnover": analytics.get("annual_turnover"),
            "num_trades": analytics.get("num_trades"),
            "trade_count": analytics.get("trade_count"),
        },
        "trade_events": trade_events,
    }


# ---------------------------------------------------------------------------
# Server-rendered HTML fragments (text/tables — exact values, print-friendly)
# ---------------------------------------------------------------------------

def _esc(v):
    return html.escape(str(v))


def _identity_items_html(result, metrics):
    ctx = result["context"]
    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    analytics = metrics.get("_raw_analytics") or {}
    items = [
        ("回测区间", f"{_esc(ctx.start_date)} → {_esc(ctx.end_date)}", ""),
        ("交易日", str(analytics.get("trading_days", "—")), ""),
        ("初始资金", _fmt_money(initial), ""),
        ("期末资产", _fmt_money(final), ""),
        ("总盈亏", f"{'+' if pnl >= 0 else ''}{_fmt_money(pnl)} 元" if abs(pnl) < 1e4 else f"{'+' if pnl >= 0 else ''}{_fmt_money(pnl)}", _pct_cls(pnl)),
        ("成交笔数", str(analytics.get("num_trades", "—")), ""),
        ("总费用", f"{_fmt_money(analytics.get('total_commission'))} 元" if _is_num(analytics.get("total_commission")) and abs(analytics.get("total_commission")) < 1e4 else _fmt_money(analytics.get("total_commission")), ""),
        ("年化换手", _fmt_pct_frac(analytics.get("annual_turnover"), 0), ""),
    ]
    out = []
    for label, value, cls in items:
        cls_attr = f" {cls}" if cls else ""
        out.append(f'<span class="id-item"><span class="id-label">{label}</span>'
                   f'<span class="id-value{cls_attr}">{value}</span></span>')
    return "".join(out)


def _dim_color(score):
    s = float(score or 0)
    if s >= 80:
        return "#26a69a"
    if s >= 60:
        return "#3987e5"
    if s >= 40:
        return "#c99700"
    return "#ef5350"


def _scorecard_html(metrics, payload):
    grade = payload["grade"]
    overall = grade.get("overall", "N/A")
    score = grade.get("score", 0)
    color = _GRADE_COLORS.get(overall, "#4c5265")
    r = 42
    circ = 2 * 3.14159265 * r
    frac = max(0.0, min(100.0, float(score or 0))) / 100.0
    dash = circ * frac
    dims = "".join(
        '<div class="dim-row">'
        f'<span class="dim-name">{_esc(d["label"])}</span>'
        f'<span class="dim-track"><span class="dim-fill" style="display:block;width:'
        f'{max(0.0, min(100.0, float(d["score"]))):.1f}%;background:{_dim_color(d["score"])}"></span></span>'
        f'<span class="dim-score">{float(d["score"]):.0f}</span>'
        "</div>"
        for d in grade.get("dimensions") or []
    )
    tags = ""
    if grade.get("strongest"):
        tags += ('<span class="sc-tag">最强维度 '
                 f'<b>{_esc(_DIM_NAMES.get(grade["strongest"], grade["strongest"]))}</b></span>')
    if grade.get("weakest"):
        tags += ('<span class="sc-tag">最弱维度 '
                 f'<b>{_esc(_DIM_NAMES.get(grade["weakest"], grade["weakest"]))}</b></span>')

    diags = payload.get("diagnostics") or []
    if not (metrics.get("_raw_analytics")):
        diag_items = '<div class="diag-empty" style="color:var(--ink-3)">数据不足，无法诊断</div>'
    elif diags:
        diag_items = "".join(
            f'<div class="diag-item {_esc(d.get("severity", ""))}">'
            f'<span class="diag-dot"></span>'
            f'<span><span class="diag-finding">{_esc(d.get("finding", ""))}</span>'
            + (f'<br><span class="diag-cause">{_esc(d["root_cause"])}</span>' if d.get("root_cause") else "")
            + "</span></div>"
            for d in diags[:4]
        )
    else:
        diag_items = '<div class="diag-empty">未发现显著瓶颈（Sharpe / 回撤 / 胜率 / Alpha 均在目标内）</div>'

    return (
        '<div class="scorecard-top">'
        f'<div class="grade-gauge"><svg width="96" height="96" viewBox="0 0 96 96" aria-hidden="true">'
        f'<circle cx="48" cy="48" r="{r}" fill="none" stroke="#2a2e39" stroke-width="6"/>'
        f'<circle cx="48" cy="48" r="{r}" fill="none" stroke="{color}" stroke-width="6" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}"/>'
        f'</svg><div class="gg-center">'
        f'<span class="gg-grade" style="color:{color}">{_esc(overall)}</span>'
        f'<span class="gg-score">{float(score or 0):.1f} / 100</span>'
        '</div></div>'
        '<div class="scorecard-headline">'
        '<div class="sh-label">策略综合评级 · 6 维加权</div>'
        f'<div class="sh-text">{_esc(grade.get("summary_text") or "—")}</div>'
        '</div></div>'
        f'<div class="dim-list">{dims}</div>'
        f'<div class="scorecard-tags">{tags}</div>'
        f'<div class="diag-list"><div class="diag-title">瓶颈诊断</div>{diag_items}</div>'
    )


def _target_chip(passed, label):
    if passed is None:
        return ""
    cls = "pass" if passed else "fail"
    mark = "✓" if passed else "✗"
    return f'<span class="kpi-target {cls}">{mark} {label}</span>'


def _kpi_band_html(result, metrics):
    a = metrics.get("_raw_analytics") or {}

    def raw(key):
        v = a.get(key)
        return v if _is_num(v) else None

    sharpe = raw("sharpe_ratio")
    max_dd = raw("max_drawdown")
    ann = raw("annual_return")
    total = raw("total_return")
    bench_total = raw("benchmark_return")
    # Excess headline uses the arithmetic-gap caliber (total − benchmark),
    # consistent with the displayed totals and _calc_metrics.
    excess_gap = (total - bench_total) if (total is not None and bench_total is not None) else None
    win_rate = raw("win_rate_trade")
    trade_count = a.get("trade_count") or 0
    plr = raw("profit_loss_ratio")

    tiles = [
        {
            "label": "总收益率", "metric": "total_return",
            "value": _fmt_pct_frac(total, 2, sign=True), "cls": _pct_cls(total),
            "sub": f"期末 {_fmt_money(result['context'].portfolio.total_value)}",
            "chip": _target_chip(None if total is None else total > 0, "为正"),
        },
        {
            "label": "年化收益率", "metric": "ann_ret",
            "value": _fmt_pct_frac(ann, 2, sign=True), "cls": _pct_cls(ann),
            "sub": f"基准 {metrics['benchmark_ret']}",
            "chip": _target_chip(None if ann is None else ann > 0, "为正"),
        },
        {
            "label": "超额收益", "metric": "excess_return",
            "value": _fmt_pct_frac(excess_gap, 2, sign=True),
            "cls": _pct_cls(excess_gap),
            "sub": f"信息比率 {metrics['info_ratio']}",
            "chip": _target_chip(None if excess_gap is None else excess_gap > 0, "跑赢基准"),
        },
        {
            "label": "Sharpe 比率", "metric": "sharpe",
            "value": metrics["sharpe"], "cls": "",
            "sub": f"Sortino {metrics['sortino']}",
            "chip": _target_chip(None if sharpe is None else sharpe >= 1.0, "≥ 1.0"),
        },
        {
            "label": "最大回撤", "metric": "max_dd",
            "value": metrics["max_dd"], "cls": "down" if (max_dd or 0) < 0 else "",
            "sub": f"Calmar {metrics['calmar']}",
            "chip": _target_chip(None if max_dd is None else max_dd >= -0.20, "≤ 20%"),
        },
        {
            "label": "交易胜率", "metric": "win_rate",
            "value": metrics["win_rate"], "cls": "",
            "sub": f"胜 {metrics['win_count']} · 负 {metrics['loss_count']}",
            "chip": _target_chip(None if trade_count < 3 else (win_rate or 0) >= 0.40, "≥ 40%"),
        },
        {
            "label": "盈亏比", "metric": "profit_loss_ratio",
            "value": metrics["profit_loss_ratio"], "cls": "",
            "sub": f"配对交易 {metrics['trade_count']} 次",
            "chip": _target_chip(None if trade_count < 1 else (plr or 0) >= 1.0, "≥ 1.0"),
        },
        {
            "label": "年化波动率", "metric": "ann_vol",
            "value": metrics["ann_vol"], "cls": "",
            "sub": f"基准 {metrics['bm_vol']}",
            "chip": "",
        },
    ]
    out = []
    for t in tiles:
        out.append(
            f'<div class="kpi" data-metric="{t["metric"]}" tabindex="0" role="button" '
            f'aria-label="{t["label"]} {t["value"]}">'
            f'<div class="kpi-label">{t["label"]}</div>'
            f'<div class="kpi-value {t["cls"]}">{t["value"]}</div>'
            f'<div class="kpi-sub">{t["sub"]}</div>{t["chip"]}</div>'
        )
    return '<div class="kpi-band">' + "".join(out) + "</div>"


def _monthly_heatmap_html(monthly):
    """Year × month grid; the table IS the chart (cells carry values)."""
    if not monthly:
        return '<div class="noscript-note">回测时间不足，无月度数据</div>'
    vals = [v for v in monthly.values() if _is_num(v)]
    if not vals:
        return '<div class="noscript-note">无月度数据</div>'
    cap = max(abs(v) for v in vals) or 1.0
    years = sorted({k[:4] for k in monthly})
    months = [f"{m:02d}" for m in range(1, 13)]

    def cell_bg(v):
        alpha = 0.10 + min(1.0, abs(v) / cap) * 0.82
        rgb = "38,166,154" if v >= 0 else "239,83,80"
        return f"background:rgba({rgb},{alpha:.2f})"

    head = ('<tr><th class="year-h">年份</th>'
            + "".join(f"<th>{int(m)}月</th>" for m in months)
            + "<th>累计</th></tr>")
    body_rows = []
    for y in years:
        tds = []
        compound = 1.0
        has_any = False
        for m in months:
            v = monthly.get(f"{y}-{m}")
            if _is_num(v):
                has_any = True
                compound *= 1 + v
                tds.append(f'<td style="{cell_bg(v)}" title="{y}-{m} · {v * 100:+.2f}%">{v * 100:+.1f}</td>')
            else:
                tds.append('<td class="empty"></td>')
        if has_any:
            ytd = compound - 1
            tds.append(f'<td class="year-total" style="{cell_bg(ytd)}">{ytd * 100:+.1f}</td>')
        else:
            tds.append('<td class="empty"></td>')
        body_rows.append(f'<tr><th class="year-h">{y}</th>{"".join(tds)}</tr>')
    caption = ('<p style="font-size:10px;color:var(--ink-3);margin-top:8px">'
               f'颜色深度与单月绝对收益成正比（区间峰值 {cap * 100:.1f}%）；'
               '绿色为正 · 红色为负，数值直接标注于单元格。</p>')
    return (f'<div class="tbl-wrap"><table class="heatmap" aria-label="月度收益热力图">'
            f'{head}{"".join(body_rows)}</table></div>{caption}')


def _risk_metrics_html(metrics):
    a = metrics.get("_raw_analytics") or {}
    de = a.get("daily_excess_return")
    daily_excess = f"{de * 100:+.2f}%" if _is_num(de) else "N/A"
    cells = [
        ("Alpha", metrics["alpha"], "alpha"),
        ("Beta", metrics["beta"], "beta"),
        ("信息比率", metrics["info_ratio"], "info_ratio"),
        ("策略年化波动", metrics["ann_vol"], "ann_vol"),
        ("基准年化波动", metrics["bm_vol"], "bm_vol"),
        ("日超额(年化)", daily_excess, "daily_excess"),
        ("超额最大回撤", metrics["excess_max_dd"], "excess_max_dd"),
        ("超额夏普", metrics["excess_sharpe"], "excess_sharpe"),
        ("日胜率", metrics["daily_win_rate"], "daily_win_rate"),
        ("配对交易", metrics["trade_count"], "trade_count"),
    ]
    note = metrics.get("benchmark_note")
    out = []
    for label, value, key in cells:
        out.append(
            f'<div class="stat-cell" data-metric="{key}" tabindex="0" role="button" aria-label="{label} {value}">'
            f'<div class="sc-k">{label}</div><div class="sc-v rm-value">{value}</div></div>'
        )
    note_html = (f'<p style="font-size:10px;color:var(--warn);padding:8px 12px 0">{_esc(note)}</span></p>'
                 if note else "")
    return '<div class="metric-rail">' + "".join(out) + "</div>" + note_html


def _dd_periods_html(periods):
    if not periods:
        return '<div class="noscript-note">回测期间无回撤（净值单调上行）或数据不足</div>'
    max_depth = max(abs(p.get("depth", 0)) for p in periods) or 1.0
    rows = []
    for i, p in enumerate(periods, 1):
        depth = p.get("depth", 0)
        bar_w = min(100.0, abs(depth) / max_depth * 100)
        recovered = p.get("recovery") is not None
        status = ('<span class="up">已修复</span>' if recovered
                  else '<span class="down">进行中</span>')
        rows.append(
            f'<tr><td>{i}</td>'
            f'<td class="l">{_esc(p.get("start", ""))}</td>'
            f'<td class="l">{_esc(p.get("trough", ""))}</td>'
            f'<td class="l">{_esc(p.get("recovery") or "—")}</td>'
            f'<td class="down">{depth * 100:.2f}%'
            f'<div style="height:3px;background:var(--bg-3);border-radius:2px;margin-top:3px">'
            f'<div style="height:100%;width:{bar_w:.0f}%;background:var(--down);border-radius:2px"></div></div></td>'
            f'<td>{p.get("duration_days", "—")}</td>'
            f'<td>{p.get("recovery_days") if p.get("recovery_days") is not None else "—"}</td>'
            f'<td>{status}</td></tr>'
        )
    return (
        '<div class="tbl-wrap"><table class="tbl"><thead><tr>'
        '<th>#</th><th class="l">开始</th><th class="l">触底</th><th class="l">修复</th>'
        '<th>深度</th><th>持续天数</th><th>修复天数</th><th>状态</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _trade_stats_html(metrics, payload):
    a = metrics.get("_raw_analytics") or {}
    ts = payload.get("trade_stats") or {}
    avg_win = ts.get("avg_win")
    avg_loss = ts.get("avg_loss")

    cells = [
        ("成交笔数", str(a.get("num_trades", "—")), None),
        ("配对交易", str(a.get("trade_count", "—")), "trade_count"),
        ("交易胜率", metrics["win_rate"], "win_rate"),
        ("盈亏比", metrics["profit_loss_ratio"], "profit_loss_ratio"),
        ("平均每笔盈利", _fmt_money(avg_win), None),
        ("平均每笔亏损", _fmt_money(avg_loss), None),
        ("总费用", _fmt_money(ts.get("total_commission")), "commission"),
        ("年化换手", _fmt_pct_frac(ts.get("annual_turnover"), 0), "turnover"),
    ]
    out = ['<div class="metric-rail metric-rail-4">']
    for label, value, key in cells:
        attr = f' data-metric="{key}" tabindex="0" role="button"' if key else ""
        out.append(
            f'<div class="stat-cell"{attr}>'
            f'<div class="sc-k">{label}</div><div class="sc-v rm-value">{value}</div></div>'
        )
    out.append("</div>")

    # Avg win vs avg loss comparison bars
    if _is_num(avg_win) and _is_num(avg_loss) and (avg_win or avg_loss):
        mx = max(abs(avg_win), abs(avg_loss)) or 1.0
        w_win = abs(avg_win) / mx * 100
        w_loss = abs(avg_loss) / mx * 100
        out.append(
            '<div style="padding:12px 14px">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
            '<span style="width:88px;font-size:10px;color:var(--ink-3)">平均盈利</span>'
            f'<div style="flex:1;height:8px;background:var(--bg-0);border-radius:4px;overflow:hidden">'
            f'<div style="height:100%;width:{w_win:.1f}%;background:var(--up);border-radius:4px"></div></div>'
            f'<span class="num up" style="width:90px;text-align:right;font-size:11px;font-weight:600">{_fmt_money(avg_win)}</span></div>'
            '<div style="display:flex;align-items:center;gap:8px">'
            '<span style="width:88px;font-size:10px;color:var(--ink-3)">平均亏损</span>'
            f'<div style="flex:1;height:8px;background:var(--bg-0);border-radius:4px;overflow:hidden">'
            f'<div style="height:100%;width:{w_loss:.1f}%;background:var(--down);border-radius:4px"></div></div>'
            f'<span class="num down" style="width:90px;text-align:right;font-size:11px;font-weight:600">{_fmt_money(avg_loss)}</span></div>'
            "</div>"
        )
    return '<div class="panel" style="margin-top:12px"><div class="panel-head"><span class="panel-title">交易统计</span></div>' + "".join(out) + "</div>"


def _positions_html(result):
    ctx = result["context"]
    positions = getattr(ctx.portfolio, "positions", {}) or {}
    total = getattr(ctx.portfolio, "total_value", 0) or 0
    rows = []
    for sec, pos in positions.items():
        amount = getattr(pos, "amount", 0) or 0
        if amount <= 0:
            continue
        avg_cost = getattr(pos, "avg_cost", 0) or 0
        price = getattr(pos, "current_price", None) or avg_cost
        mv = getattr(pos, "total_value", None)
        if not _is_num(mv):
            mv = amount * price if _is_num(price) else 0
        weight = mv / total * 100 if total else 0
        upl = (price - avg_cost) * amount if _is_num(price) and _is_num(avg_cost) else None
        upl_pct = (price / avg_cost - 1) * 100 if avg_cost else None
        rows.append(
            f'<tr><td class="l">{_esc(sec)}</td>'
            f'<td>{amount:,}</td>'
            f'<td>{getattr(pos, "closeable_amount", 0):,}</td>'
            f'<td>{avg_cost:.3f}</td><td>{price:.3f}</td>'
            f'<td>{_fmt_money(mv)}</td><td>{weight:.1f}%</td>'
            f'<td class="{_pct_cls(upl)}">{_fmt_money(upl)}</td>'
            f'<td class="{_pct_cls(upl_pct)}">{"" if upl_pct is None else f"{upl_pct:+.2f}%"}</td></tr>'
        )
    if not rows:
        return '<div class="noscript-note">空仓（期末无持仓）</div>'
    return (
        '<div class="tbl-wrap"><table class="tbl"><thead><tr>'
        '<th class="l">标的</th><th>持仓</th><th>可卖</th><th>成本价</th><th>最新价</th>'
        '<th>市值</th><th>权重</th><th>浮动盈亏</th><th>盈亏 %</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _trade_table_html(result):
    trade_log = result.get("trade_log") or []
    rows = []
    i = 0
    for t in trade_log:
        ttype = t.get("type")
        if ttype in ("BUY", "SELL"):
            i += 1
            price = t.get("price")
            amount = t.get("amount") or 0
            value = price * amount if _is_num(price) and _is_num(amount) else None
            dir_cls = "up" if ttype == "BUY" else "down"
            dir_txt = "买入" if ttype == "BUY" else "卖出"
            rows.append(
                f'<tr><td data-v="{i}">{i}</td>'
                f'<td class="l" data-v="{_esc(_to_tv_date(t.get("date")))}">{_esc(_to_tv_date(t.get("date")))}</td>'
                f'<td class="{dir_cls}" data-v="{ttype}">{dir_txt}</td>'
                f'<td class="l">{_esc(t.get("security", ""))}</td>'
                f'<td data-v="{price if _is_num(price) else ""}">{f"{price:.3f}" if _is_num(price) else "—"}</td>'
                f'<td data-v="{amount}">{amount:,}</td>'
                f'<td data-v="{value if _is_num(value) else ""}">{_fmt_money(value)}</td>'
                f'<td data-v="{t.get("commission", 0) or 0}">{(t.get("commission") or 0):.2f}</td>'
                f'<td class="l muted">{"部分成交" if t.get("partial") else ""}</td></tr>'
            )
        else:
            label = {"ORDER_TIMEOUT": "超时撤单", "DELIST_LIQUIDATE": "退市清算"}.get(ttype, str(ttype))
            note = t.get("reason") or t.get("action") or ""
            rows.append(
                f'<tr><td data-v="0" class="muted">—</td>'
                f'<td class="l muted" data-v="{_esc(_to_tv_date(t.get("date")))}">{_esc(_to_tv_date(t.get("date")))}</td>'
                f'<td class="muted" data-v="{_esc(label)}">{_esc(label)}</td>'
                f'<td class="l muted">{_esc(t.get("security", ""))}</td>'
                '<td class="muted">—</td><td class="muted">—</td><td class="muted">—</td><td class="muted">—</td>'
                f'<td class="l muted">{_esc(note)}</td></tr>'
            )
    if not rows:
        return '<div class="noscript-note">回测期间未执行任何交易</div>'
    return (
        '<div class="tbl-wrap tbl-scroll"><table class="tbl" id="tradeTable"><thead><tr>'
        '<th class="sortable" data-type="num">#</th>'
        '<th class="l sortable" data-type="str">日期</th>'
        '<th class="sortable" data-type="str">方向</th>'
        '<th class="l">标的</th>'
        '<th class="sortable" data-type="num">价格</th>'
        '<th class="sortable" data-type="num">数量</th>'
        '<th class="sortable" data-type="num">金额</th>'
        '<th class="sortable" data-type="num">佣金</th>'
        '<th class="l">备注</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _calendar_table_html(result, chart):
    cum = chart.get("cum_return_data") or []
    if not cum:
        return '<div class="noscript-note">无净值数据</div>'
    dd_by_date = {p["time"]: p["value"] for p in chart.get("drawdown_data") or []}
    trade_map = {}
    for t in result.get("trade_log") or []:
        d = _to_tv_date(t.get("date"))
        ttype = t.get("type")
        if ttype in ("BUY", "SELL"):
            action = "买入" if ttype == "BUY" else "卖出"
            txt = f"{action} {_esc(t.get('security', ''))} {t.get('amount', 0):,}股"
            if _is_num(t.get("price")):
                txt += f" @{t['price']:.3f}"
            trade_map.setdefault(d, []).append((ttype, txt))
        else:
            label = {"ORDER_TIMEOUT": "超时撤单", "DELIST_LIQUIDATE": "退市清算"}.get(ttype, str(ttype))
            trade_map.setdefault(d, []).append(("EVT", f"{label} {_esc(t.get('security', ''))}"))
    rows = []
    for p in cum:
        d = p["time"]
        ret = p["value"]
        dd = dd_by_date.get(d)
        ops = trade_map.get(d, [])
        if ops:
            op_html = "<br>".join(
                f'<span class="{"up" if k == "BUY" else ("down" if k == "SELL" else "muted")}">{txt}</span>'
                for k, txt in ops
            )
        else:
            op_html = '<span class="muted">—</span>'
        rows.append(
            f'<tr><td class="l">{d}</td>'
            f'<td class="{_pct_cls(ret)}">{ret:+.2f}%</td>'
            f'<td class="{_pct_cls(dd) if dd else "muted"}">{f"{dd:+.2f}%" if _is_num(dd) else "—"}</td>'
            f'<td class="l">{op_html}</td></tr>'
        )
    return (
        '<div class="tbl-wrap tbl-scroll"><table class="tbl"><thead><tr>'
        '<th class="l">日期</th><th>累计收益</th><th>回撤</th><th class="l">当日操作</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _twin(summary, headers, rows):
    """Accessible table twin for a chart (collapsible)."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return (f'<details class="twin"><summary>{summary}</summary><div class="twin-body">'
            f'<div class="tbl-wrap"><table class="tbl">{head}{body}</table></div></div></details>')


def _sampled(seq, limit=40):
    if len(seq) <= limit:
        return list(seq)
    step = (len(seq) - 1) / (limit - 1)
    return [seq[round(i * step)] for i in range(limit)]


def _annual_twin_html(payload):
    rows = []
    for r in payload.get("annual") or []:
        rows.append([
            _esc(r["year"]),
            f'<span class="{_pct_cls(r["strategy"])}">{_fmt_pct_frac(r["strategy"], 2, True)}</span>',
            (f'<span class="{_pct_cls(r["benchmark"])}">{_fmt_pct_frac(r["benchmark"], 2, True)}</span>'
             if r.get("benchmark") is not None else "—"),
            (f'<span class="{_pct_cls(r["excess"])}">{_fmt_pct_frac(r["excess"], 2, True)}</span>'
             if r.get("excess") is not None else "—"),
        ])
    if not rows:
        return ""
    return _twin("查看年度数据表", ["年份", "策略", "基准", "超额"], rows)


def _rolling_twin_html(payload):
    rs = payload.get("rolling", {}).get("sharpe") or []
    rv = {p["t"]: p["v"] for p in payload.get("rolling", {}).get("vol") or []}
    rows = []
    for p in _sampled(rs, 40):
        v = rv.get(p["t"])
        rows.append([_esc(p["t"]), f"{p['v']:.3f}", f"{v * 100:.2f}%" if _is_num(v) else "—"])
    if not rows:
        return ""
    return _twin("查看滚动指标数据表（抽样）", ["日期", "滚动 Sharpe", "滚动波动率"], rows)


def _excess_twin_html(payload, metrics):
    excess = payload.get("excess") or []
    dates = payload.get("dates") or []
    pairs = [(d, v) for d, v in zip(dates, excess) if _is_num(v)]
    if not pairs:
        return ""
    rows = [[_esc(d), f'<span class="{_pct_cls(v)}">{v:+.3f}%</span>'] for d, v in _sampled(pairs, 40)]
    return _twin("查看累计超额数据表（抽样）", ["日期", "累计超额"], rows)


def _alloc_twin_html(payload):
    dates = payload.get("dates") or []
    cash = payload.get("allocation", {}).get("cash") or []
    inv = payload.get("allocation", {}).get("invested") or []
    rows = []
    pts = []
    for i, d in enumerate(dates):
        c = cash[i] if i < len(cash) else None
        v = inv[i] if i < len(inv) else None
        if _is_num(c) and _is_num(v):
            pts.append((d, c, v))
    for d, c, v in _sampled(pts, 40):
        tot = c + v
        rows.append([_esc(d), _fmt_money(v), _fmt_money(c), _fmt_money(tot),
                     f"{v / tot * 100:.1f}%" if tot else "—"])
    if not rows:
        return ""
    return _twin("查看资产构成数据表（抽样）", ["日期", "持仓市值", "现金", "总资产", "仓位"], rows)


def _per_stock_twin_html(payload):
    rows = []
    for r in payload.get("per_stock_pnl") or []:
        rows.append([_esc(r["sec"]),
                     f'<span class="{_pct_cls(r["pnl"])}">{_fmt_money(r["pnl"])}</span>'])
    if not rows:
        return ""
    return _twin("查看个股盈亏数据表", ["标的", "净盈亏"], rows)


def _dist_stats_html(payload):
    s = payload.get("dist", {}).get("stats") or {}
    if not s:
        return ""
    cells = [
        ("均值", _fmt_pct_frac(s.get("mean"), 3, True)),
        ("标准差", _fmt_pct_frac(s.get("std"), 3)),
        ("偏度", f"{s.get('skewness', 0):.2f}" if _is_num(s.get("skewness")) else "—"),
        ("峰度", f"{s.get('kurtosis', 0):.2f}" if _is_num(s.get("kurtosis")) else "—"),
        ("最佳单日", _fmt_pct_frac(s.get("best_day"), 2, True)),
        ("最差单日", _fmt_pct_frac(s.get("worst_day"), 2, True)),
        ("上涨天数", str(s.get("positive_days", "—"))),
        ("下跌天数", str(s.get("negative_days", "—"))),
    ]
    return '<div class="stat-rail">' + "".join(
        f'<div class="stat-cell"><div class="sc-k">{k}</div><div class="sc-v">{v}</div></div>'
        for k, v in cells
    ) + "</div>"


def _method_blocks_html(result, metrics, payload):
    benchmark = result.get("benchmark", "000300.XSHG")
    bench_code = payload["meta"]["benchmark_code"]
    bench_label = payload["meta"]["benchmark_label"]
    portfolio = result["context"].portfolio
    open_c = getattr(portfolio, "open_commission", None)
    close_c = getattr(portfolio, "close_commission", None)
    close_tax = getattr(portfolio, "close_tax", None)
    min_c = getattr(portfolio, "min_commission", None)
    cost_bits = []
    if _is_num(open_c):
        cost_bits.append(f"买入佣金 {open_c * 100:.3f}%")
    if _is_num(close_c):
        cost_bits.append(f"卖出佣金 {close_c * 100:.3f}%")
    if _is_num(close_tax):
        cost_bits.append(f"印花税 {close_tax * 100:.2f}%（卖出）")
    if _is_num(min_c):
        cost_bits.append(f"最低佣金 {min_c:.0f} 元")
    cost_text = "；".join(cost_bits) if cost_bits else "按回测引擎配置的交易成本执行"

    bench_note = metrics.get("benchmark_note")
    bench_note_html = f"<p><strong>注意：</strong>{_esc(bench_note)}</p>" if bench_note else ""

    return f"""
<div class="method-block">
  <h4>数据来源</h4>
  <ul>
    <li>行情数据：AKShare（A 股日线，前复权 qfq）</li>
    <li>基准：{_esc(bench_label)}（{_esc(bench_code)}），与策略同日对齐</li>
    <li>净值序列：回测引擎逐日盯市记录（收盘价）</li>
  </ul>
</div>
<div class="method-block">
  <h4>回测口径</h4>
  <ul>
    <li>成交价：信号次日开盘价，无未来函数</li>
    <li>T+1：当日买入次日可卖；涨跌停无法成交</li>
    <li>费用：{_esc(cost_text)}</li>
    <li>年化参数：无风险利率 {RISK_FREE_RATE * 100:.0f}%，每年 {TRADING_DAYS_PER_YEAR} 个交易日</li>
  </ul>
</div>
<div class="method-block">
  <h4>指标口径</h4>
  <ul>
    <li>Sharpe / Sortino：(日均收益 − 日无风险利率) / 波动 × √{TRADING_DAYS_PER_YEAR}</li>
    <li>Alpha / Beta / 信息比率：与基准收益同源同口径（引擎记录序列）</li>
    <li>胜率 / 盈亏比：FIFO 配对往返交易，扣除双边费用后的净盈亏</li>
    <li>点击任意指标卡片可查看完整定义与解读</li>
  </ul>
  {bench_note_html}
</div>
<div class="method-block">
  <h4>评级方法</h4>
  <ul>
    <li>6 维加权：收益 20% · 风控 20% · 风险调整 20% · 交易质量 15% · 超额 15% · 稳定性 10%</li>
    <li>评级分档：S ≥ 85 · A ≥ 70 · B ≥ 55 · C ≥ 40 · D &lt; 40</li>
    <li>瓶颈诊断基于目标线：Sharpe ≥ 1.0 · 回撤 ≤ 20% · 胜率 ≥ 40% · Alpha ≥ 0</li>
  </ul>
</div>
<div class="method-block">
  <h4>图表标记说明</h4>
  <ul>
    <li>净值曲线上的绿点 / 红点：当日买入 / 卖出成交</li>
    <li>K 线金色描边：触及涨停（按板块阈值估算：主板 10% · 创业板/科创板 20% · 北交所 30%）</li>
    <li>净值图浅红色区域：Top 3 回撤区间（按深度）</li>
    <li>回撤子图红点：最大回撤触底点</li>
  </ul>
</div>
"""


def generate_html_report(result, out_path):
    """Generate the self-contained interactive HTML report.

    Single-file output: inline CSS/JS, hand-rolled SVG charts, all numbers
    computed in Python. No CDN, no network — works fully offline.
    """
    ctx = result["context"]
    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    chart = _compute_chart_data(result)

    # Benchmark series for metrics (single caliber: engine-recorded values)
    recorded = result["recorded_values"]
    bench_data = _benchmark_returns_from_result(result, recorded)
    if not bench_data:
        bench_data = _fetch_benchmark_returns(result.get("benchmark", "000300.XSHG"),
                                              ctx.start_date, ctx.end_date, recorded)

    metrics = _calc_metrics(result, bench_data)
    payload = _build_report_payload(result, chart, metrics, bench_data)

    data_json = _json_for_script(payload)
    template = _load_report_asset("report.html")
    css = _load_report_asset("report.css")
    js = _load_report_asset("report.js")

    symbol = payload["meta"]["symbol"]
    tokens = {
        "%%TITLE%%": _esc(f"EasyQuant 回测报告 · {symbol} · {ctx.start_date} ~ {ctx.end_date}"),
        "%%CSS%%": css,
        "%%JS%%": js,
        "%%DATA_JSON%%": data_json,
        "%%BRAND_LOCKUP%%": html_header_brand_lockup(),
        "%%BRAND_FOOTER%%": html_footer_brand_chip(),
        "%%SYMBOL%%": _esc(symbol),
        "%%START_DATE%%": _esc(str(ctx.start_date)),
        "%%END_DATE%%": _esc(str(ctx.end_date)),
        "%%PNL_PCT%%": f"{pnl_pct:+.2f}%",
        "%%PNL_BADGE_CLASS%%": "pos" if pnl >= 0 else "neg",
        "%%IDENTITY_ITEMS%%": _identity_items_html(result, metrics),
        "%%SCORECARD%%": _scorecard_html(metrics, payload),
        "%%KPI_BAND%%": _kpi_band_html(result, metrics),
        "%%MONTHLY_HEATMAP%%": _monthly_heatmap_html(payload.get("monthly") or {}),
        "%%DIST_STATS%%": _dist_stats_html(payload),
        "%%ANNUAL_TWIN%%": _annual_twin_html(payload),
        "%%ROLLING_TWIN%%": _rolling_twin_html(payload),
        "%%EXCESS_TWIN%%": _excess_twin_html(payload, metrics),
        "%%RISK_METRICS%%": _risk_metrics_html(metrics),
        "%%DD_PERIODS%%": _dd_periods_html(payload.get("drawdown_periods") or []),
        "%%ALLOC_TWIN%%": _alloc_twin_html(payload),
        "%%TRADE_HEAD_NOTE%%": f"成交 {payload['trade_stats'].get('num_trades') or 0} 笔 · "
                               f"配对 {payload['trade_stats'].get('trade_count') or 0} 次 · "
                               f"费用 {_fmt_money(payload['trade_stats'].get('total_commission'))}",
        "%%TRADE_STATS%%": _trade_stats_html(metrics, payload),
        "%%PER_STOCK_TWIN%%": _per_stock_twin_html(payload),
        "%%POSITIONS%%": _positions_html(result),
        "%%POSITIONS_SUB%%": f"{len([p for p in (ctx.portfolio.positions or {}).values() if getattr(p, 'amount', 0) > 0])} 只",
        "%%TRADE_TABLE%%": _trade_table_html(result),
        "%%CALENDAR%%": _calendar_table_html(result, chart),
        "%%METHOD_BLOCKS%%": _method_blocks_html(result, metrics, payload),
        "%%GENERATED_AT%%": payload["meta"]["generated_at"],
    }
    html_doc = template
    for token, value in tokens.items():
        html_doc = html_doc.replace(token, str(value))
    leftovers = [t for t in ("%%TITLE%%", "%%CSS%%", "%%JS%%", "%%DATA_JSON%%") if t in html_doc]
    if leftovers:
        raise RuntimeError(f"HTML template tokens not replaced: {leftovers}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

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
            "benchmark_note": "",
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
    chart_benchmark_return = None
    if bench_data:
        try:
            final_benchmark_pct = float(bench_data[-1]["value"])
        except (KeyError, TypeError, ValueError, OverflowError):
            final_benchmark_pct = float("nan")
        if np.isfinite(final_benchmark_pct):
            chart_benchmark_return = final_benchmark_pct / 100.0

    # ── Unified benchmark caliber ────────────────────────────────────────
    # All quantitative benchmark metrics (headline return, excess, alpha,
    # beta, IR) share ONE source: analyze_returns, which uses the
    # engine-recorded benchmark series.  The chart series only backfills the
    # headline card when analytics has no benchmark at all (e.g. <2 common
    # days); in that case the card is explicitly marked as chart-caliber.
    analytics_bench = analytics.get("benchmark_return")
    if analytics_bench is not None and np.isfinite(analytics_bench):
        bench_ret = float(analytics_bench)
        bench_source = "engine"
    elif chart_benchmark_return is not None:
        bench_ret = chart_benchmark_return
        bench_source = "chart"
    else:
        bench_ret = None
        bench_source = None

    report_analytics = dict(analytics)
    if bench_source == "chart":
        report_analytics["benchmark_return"] = bench_ret
        report_analytics["excess_return"] = total_ret - bench_ret

    excess_ret = total_ret - bench_ret if bench_ret is not None else None

    def _pct(value, fmt="{:.2%}"):
        return fmt.format(value) if value is not None and np.isfinite(value) else "N/A"

    def _num(value, fmt="{:.2f}"):
        return fmt.format(value) if value is not None and np.isfinite(value) else "N/A"

    if bench_source == "chart":
        benchmark_note = "基准指标不可用，卡片值为图表口径"
    elif bench_source is None:
        benchmark_note = "基准数据不可用"
    else:
        benchmark_note = ""

    alpha_v = analytics.get("alpha")
    beta_v = analytics.get("beta")
    info_v = analytics.get("information_ratio")

    return {
        "sharpe": f"{analytics['sharpe_ratio']:.2f}",
        "sortino": f"{analytics['sortino_ratio']:.2f}",
        "max_dd": f"{analytics['max_drawdown']:.2%}",
        "max_dd_pct": f"{analytics['max_drawdown']:+.2f}%",
        "ann_ret": f"{ann_ret:.2%}",
        "ann_ret_pct": f"{ann_ret:+.2f}%",
        "win_rate": f"{analytics['win_rate_trade']:.0%}",
        "daily_win_rate": f"{analytics['win_rate_daily']:.1%}",
        "benchmark_ret": _pct(bench_ret),
        "benchmark_ret_pct": _pct(bench_ret, "{:+.2f}%"),
        "benchmark_note": benchmark_note,
        "alpha": _pct(alpha_v, "{:+.2%}"),
        "beta": _num(beta_v, "{:.3f}"),
        "excess_return": _pct(excess_ret),
        "excess_return_pct": _pct(excess_ret, "{:+.2f}%"),
        "calmar": f"{analytics['calmar_ratio']:.2f}",
        "info_ratio": _num(info_v),
        "excess_max_dd": _pct(analytics.get('excess_return_max_drawdown')),
        "excess_sharpe": _num(analytics.get('excess_return_sharpe')),
        "daily_excess": _pct(analytics.get('daily_excess_return'), "{:+.4%}"),
        "profit_loss_ratio": ("∞" if analytics.get('profit_loss_ratio', 0) == float('inf')
                              else f"{analytics.get('profit_loss_ratio', 0):.2f}"),
        "win_count": str(analytics.get("win_count", 0)),
        "loss_count": str(analytics.get("loss_count", 0)),
        "ann_vol": f"{analytics['annual_volatility']:.2%}",
        "bm_vol": _pct(analytics.get('benchmark_volatility')),
        "trade_count": str(analytics.get("trade_count", 0)),
        # For benchmark return chart (configured benchmark cumulative return %)
        "bench_last": f"{bench_data[-1]['value'] if bench_data else 0:.2f}",
        # Grade data for HTML template
        "grade_data": _calc_strategy_score(report_analytics),
        # Raw analytics for HTML template (avoid redundant analyze_returns call)
        "_raw_analytics": report_analytics,
    }





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

    # Unified benchmark caliber: prefer the analytics value (engine-recorded
    # benchmark series, same source as alpha/beta); only when unavailable,
    # fall back to a direct fetch for the headline benchmark return line.
    bench_data = {}
    _analytics_bench = analytics.get("benchmark_return") if analytics else None
    if _analytics_bench is not None and np.isfinite(_analytics_bench):
        bench_data["return"] = float(_analytics_bench) * 100
        bench_data["source"] = "engine"
    else:
        try:
            bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
            if not bench_df.empty and "close" in bench_df.columns:
                bench_init = bench_df["close"].iloc[0]
                bench_final = bench_df["close"].iloc[-1]
                bench_data["return"] = (bench_final - bench_init) / bench_init * 100
                bench_data["source"] = "fetch"
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

        def _md_pct(value, fmt="{:+.2%}"):
            return fmt.format(value) if value is not None and np.isfinite(value) else "N/A"

        def _md_num(value, fmt="{:.2f}"):
            return fmt.format(value) if value is not None and np.isfinite(value) else "N/A"

        ann_ret = analytics["annual_return"]
        bench_ret_pct = bench_data["return"] / 100 if "return" in bench_data else None
        bench_cell = _md_pct(bench_ret_pct)
        delta_cell = _md_pct(ann_ret - bench_ret_pct) if bench_ret_pct is not None else "N/A"
        lines.append(f"| Annual Return | {ann_ret:+.2%} | {bench_cell} | {delta_cell} |")
        bm_vol_str = _md_pct(analytics.get("benchmark_volatility"), "{:.2%}")
        lines.append(f"| Annual Volatility | {analytics['annual_volatility']:.2%} | {bm_vol_str} | |")
        lines.append(f"| Sharpe Ratio | {analytics['sharpe_ratio']:.2f} | — | — |")
        lines.append(f"| Sortino Ratio | {analytics['sortino_ratio']:.2f} | — | — |")
        lines.append(f"| Max Drawdown | {analytics['max_drawdown']:.2%} | — | — |")
        lines.append(f"| Calmar Ratio | {analytics['calmar_ratio']:.2f} | — | — |")
        lines.append(f"| Alpha | {_md_pct(analytics.get('alpha'))} | — | — |")
        lines.append(f"| Beta | {_md_num(analytics.get('beta'))} | — | — |")
        lines.append(f"| Information Ratio | {_md_num(analytics.get('information_ratio'))} | — | — |")
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

    # ── Brinson Attribution (single-period BHB, mathematically closed) ────
    br = brinson_attribution(result)
    if br:
        lines.append("## Brinson Attribution")
        lines.append("")
        model = br.get("benchmark_model", "universe_equal_weight")
        model_label = ("universe equal-weight buy&hold"
                       if model == "universe_equal_weight" else "caller-supplied series")
        lines.append(f"*Single-period BHB decomposition; benchmark model: {model_label}. "
                     "The three effects always sum to the total active return.*")
        lines.append("")
        lines.append("| Component | Effect |")
        lines.append("|-----------|--------|")
        lines.append(f"| Allocation effect | {br['allocation_effect']:+.2%} |")
        lines.append(f"| Selection effect | {br['selection_effect']:+.2%} |")
        lines.append(f"| Interaction effect | {br['interaction_effect']:+.2%} |")
        lines.append(f"| **Total active return** | **{br['total_active_return']:+.2%}** |")
        lines.append(f"| Portfolio return | {br['portfolio_return']:+.2%} |")
        lines.append(f"| Benchmark return | {br['benchmark_return']:+.2%} |")
        lines.append("")
        sectors = br.get("sectors") or {}
        if len(sectors) > 1:
            lines.append("### Sector Breakdown")
            lines.append("")
            lines.append("| Sector | w_p | w_b | r_p | r_b | Allocation | Selection | Interaction |")
            lines.append("|--------|-----|-----|-----|-----|------------|-----------|-------------|")
            for sec_name, row in sectors.items():
                lines.append(
                    f"| {sec_name} | {row['weight_portfolio']:.1%} | {row['weight_benchmark']:.1%} "
                    f"| {row['return_portfolio']:+.2%} | {row['return_benchmark']:+.2%} "
                    f"| {row['allocation']:+.2%} | {row['selection']:+.2%} | {row['interaction']:+.2%} |"
                )
            lines.append("")

    # ── Data Sources ────────────────────────────────────────────────
    lines.append("## Data Sources")
    lines.append("")
    lines.append("| Source | Details |")
    lines.append("|--------|---------|")
    lines.append("| Market Data | AKShare `stock_zh_a_hist` (EastMoney), forward-adjusted daily OHLCV |")
    lines.append("| Benchmark | CSI 300 / SSE Composite via AKShare `stock_zh_index_daily_em` |")
    lines.append("| Risk-Free Rate | 3.0% per annum, daily = 3% / 244 |")
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

    # Benchmark data — unified caliber: prefer the analytics value (same
    # engine-recorded benchmark series behind alpha/beta); fall back to a
    # direct fetch only when analytics has no benchmark.
    bench_return = None
    _analytics_bench = analytics.get("benchmark_return") if analytics else None
    if _analytics_bench is not None and np.isfinite(_analytics_bench):
        bench_return = float(_analytics_bench)
    else:
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
        # Benchmark-dependent metrics may be None/NaN when the benchmark is
        # unavailable — report them as "unknown", never as pass/fail.
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        if value is None:
            targets.append({
                "metric": metric_name, "value": None,
                "target": target_def, "pass": None,
                "gap": "n/a (unavailable)", "priority": None,
            })
            continue
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

    # Sort: failing first by priority, then unknown, then passing
    targets.sort(key=lambda t: (t["pass"] is not False, t.get("priority") or 999))

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

    report["data_diagnostics"] = collect_data_diagnostics(result)

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
            k: (round(v, 6) if isinstance(v, float) and np.isfinite(v) else
                None if isinstance(v, float) else v)
            for k, v in br.items()
            if k != "sectors"
        }
        report["brinson_attribution"]["sectors"] = {
            sec_name: {
                kk: (round(vv, 6) if isinstance(vv, float) and np.isfinite(vv) else
                     None if isinstance(vv, float) else vv)
                for kk, vv in row.items()
            }
            for sec_name, row in (br.get("sectors") or {}).items()
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
        json.dump(
            _sanitize_json_value(report),
            f,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

    print(f"Data saved: {out_path}")
