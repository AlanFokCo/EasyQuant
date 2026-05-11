"""Report generation: chart (PNG), HTML (TradingView lightweight-charts), JSON, and Markdown."""

import os
import json
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["font.sans-serif"] = ["PingFang HK", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

from eqlib.data import fetch_stock_data, get_price
from eqlib.constants import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
import pandas as pd
import numpy as np


def _to_tv_date(date_val):
    """Convert date/datetime to lightweight-charts time string (YYYY-MM-DD)."""
    if isinstance(date_val, datetime.datetime):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, datetime.date):
        return date_val.strftime("%Y-%m-%d")
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
                "color": "#f5222d" if daily_pnl >= 0 else "#52c41a",
            })
            ret_bars.append({
                "time": d, "value": daily_ret,
                "color": "#f5222d" if daily_ret >= 0 else "#52c41a",
            })
        else:
            pnl_bars.append({"time": d, "value": 0, "color": "#484f58"})
            ret_bars.append({"time": d, "value": 0, "color": "#484f58"})
        prev_val = val

    return pnl_bars, ret_bars


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
    """Generate professional backtest chart:
    - Top: strategy cumulative return (%) vs benchmark (%)
    - Bottom: portfolio drawdown (%)
    - Key metrics annotation box
    """
    from eqlib.attribution import analyze_returns
    from eqlib.data import fetch_stock_data

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    analytics = analyze_returns(result)

    # --- Portfolio value series ---
    pf_entries = sorted(
        recorded.values(), key=lambda x: x.get("date", datetime.date.min)
    ) if isinstance(recorded, dict) else recorded
    pf_records = [r for r in pf_entries if "total_value" in r]
    if not pf_records:
        from eqlib.logger import log as _log
        _log.warning("generate_chart: no portfolio value data found in recorded_values")
        plt.close()
        return

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    pf_dates = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in pf_records])
    pf_values = pd.Series([r["total_value"] for r in pf_records], index=pf_dates)
    strat_cum_ret = (pf_values / initial - 1) * 100  # percentage

    # --- Benchmark cumulative return ---
    bench_cum_ret = None
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_df = bench_df.sort_index()
            bench_dates = bench_df.index
            bench_init = bench_df["close"].iloc[0]
            bench_cum_ret = pd.Series(
                (bench_df["close"] / bench_init - 1) * 100,
                index=bench_dates,
            )
    except Exception:
        pass

    # --- Figure ---
    fig, (ax, ax_dd) = plt.subplots(
        2, 1, figsize=(14, 8),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    fig.subplots_adjust(hspace=0.08, left=0.08, right=0.96, top=0.94, bottom=0.08)

    # Strategy return
    strat_dates_np = pf_dates.to_numpy()
    ax.plot(strat_dates_np, strat_cum_ret.values, color="#1976D2", linewidth=1.8,
            label="Strategy", zorder=5)

    # Benchmark return
    bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    if bench_cum_ret is not None:
        ax.plot(bench_cum_ret.index.to_numpy(), bench_cum_ret.values, color="#757575",
                linewidth=1.2, alpha=0.7, label=bench_label, zorder=4)

    # Zero line
    ax.axhline(0, color="#555555", linewidth=0.6, linestyle="--", zorder=0)

    # Buy/sell trade markers (sparse if too many)
    buys = [t for t in trade_log if t["type"] == "BUY"]
    sells = [t for t in trade_log if t["type"] == "SELL"]
    if len(buys) <= 50:
        for b in buys:
            ret_at_buy = (pf_values.reindex([pd.Timestamp(b["date"])], method="nearest").iloc[0] / initial - 1) * 100
            ax.plot(b["date"], ret_at_buy, marker="^", color="#2E7D32",
                    markersize=5, zorder=3)
    if len(sells) <= 50:
        for s in sells:
            ret_at_sell = (pf_values.reindex([pd.Timestamp(s["date"])], method="nearest").iloc[0] / initial - 1) * 100
            ax.plot(s["date"], ret_at_sell, marker="v", color="#C62828",
                    markersize=5, zorder=3)

    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_ylabel("Cumulative Return (%)", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_title(
        f"PnL: {pnl:+,.0f} ({pnl_pct:+.2f}%)  |  Trades: {len(trade_log)}",
        fontsize=12, fontweight="bold",
    )

    # Metrics annotation
    if analytics:
        ann_ret = analytics.get("annual_return", 0.0)
        sharpe = analytics.get("sharpe_ratio", 0.0)
        max_dd = analytics.get("max_drawdown", 0.0)
        win = analytics.get("win_rate", 0.0)
        beta = analytics.get("beta", 1.0)
        alpha = analytics.get("alpha", 0.0)
        ax.text(
            0.98, 0.03,
            f"Ann.Ret  {ann_ret:+.2%}    Sharpe  {sharpe:.2f}    MaxDD  {max_dd:.2%}\n"
            f"Beta     {beta:.2f}      Alpha   {alpha:+.2%}   Win    {win:.1%}",
            transform=ax.transAxes, fontsize=9, fontfamily="monospace",
            ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                      edgecolor="#bbbbbb", alpha=0.9),
        )

    # --- Drawdown panel ---
    rolling_max = pf_values.cummax()
    dd_pct = (pf_values - rolling_max) / rolling_max * 100
    ax_dd.fill_between(dd_pct.index.to_numpy(), dd_pct.values, 0, color="#EF5350",
                       alpha=0.4, zorder=2)
    ax_dd.axhline(0, color="#555555", linewidth=0.6, linestyle="--")
    ax_dd.set_ylabel("Drawdown (%)", fontsize=10)
    ax_dd.grid(True, alpha=0.3)
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax_dd.xaxis.set_major_locator(mdates.MonthLocator(interval=max(1, len(pf_dates) // 12)))

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved: {out_path}")


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
    pnl_pct = (pnl / initial) * 100

    # Collect traded securities
    securities = set()
    for t in trade_log:
        securities.add(t["security"])
    if not securities and ctx.universe:
        securities.add(ctx.universe[0])
    if not securities:
        securities.add("601390")

    symbol = list(securities)[0]

    # ============================================================
    # K-line + technical indicators (use preloaded OHLCV first)
    # ============================================================
    candlestick_data = []
    ma5_data = []
    ma20_data = []
    ma60_data = []
    volume_data = []
    support_data = []
    resistance_data = []

    ohlcv_data = result.get("ohlcv_data", {})
    if symbol in ohlcv_data:
        df = ohlcv_data[symbol]
    else:
        df = pd.DataFrame()
        try:
            df = fetch_stock_data(symbol, start, end)
        except Exception:
            pass
    if not df.empty:
        # Trim OHLCV to backtest period so K-line aligns with return charts
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        df_sorted = df.sort_index()
        df_sorted = df_sorted.loc[start_ts:end_ts]
        if df_sorted.empty:
            df_sorted = df.sort_index()
        closes = df_sorted["close"]
        highs = df_sorted["high"]
        lows = df_sorted["low"]
        ma5 = closes.rolling(5).mean()
        ma20 = closes.rolling(20).mean()
        ma60 = closes.rolling(60).mean()
        support, resistance = _compute_support_resistance(closes, highs, lows, window=20)

        for (date, row), m5, m20, m60, sup, res in zip(
                df_sorted.iterrows(), ma5, ma20, ma60, support, resistance):
            d = _to_tv_date(date)
            o = float(row.get("open", 0))
            h = float(row.get("high", 0))
            l = float(row.get("low", 0))
            c = float(row.get("close", 0))
            v = float(row.get("volume", 0))

            candlestick_data.append({
                "time": d, "open": round(o, 3), "high": round(h, 3),
                "low": round(l, 3), "close": round(c, 3),
            })
            volume_data.append({
                "time": d, "value": round(v, 0),
                "color": "#26a69a" if c >= o else "#ef5350",
            })
            if not pd.isna(m5):
                ma5_data.append({"time": d, "value": round(float(m5), 3)})
            if not pd.isna(m20):
                ma20_data.append({"time": d, "value": round(float(m20), 3)})
            if not pd.isna(m60):
                ma60_data.append({"time": d, "value": round(float(m60), 3)})
            if not pd.isna(sup):
                support_data.append({"time": d, "value": round(float(sup), 3)})
            if not pd.isna(res):
                resistance_data.append({"time": d, "value": round(float(res), 3)})

    # ============================================================
    # Buy/sell markers
    # ============================================================
    markers = []
    for t in trade_log:
        markers.append({
            "time": _to_tv_date(t["date"]),
            "position": "belowBar" if t["type"] == "BUY" else "aboveBar",
            "color": "#26a69a" if t["type"] == "BUY" else "#ef5350",
            "shape": "arrowUp" if t["type"] == "BUY" else "arrowDown",
            "text": f"{'买' if t['type'] == 'BUY' else '卖'} {t['amount']}",
        })
    markers.sort(key=lambda x: x["time"])

    # ============================================================
    # Cumulative return series (strategy)
    # ============================================================
    cum_return_data = _build_return_series(recorded, initial)

    # ============================================================
    # Daily P&L and daily return
    # ============================================================
    pnl_bar_data, daily_returns_data = _build_daily_pnl(recorded, initial)

    # ============================================================
    # Benchmark returns (uses the configured benchmark from result)
    # ============================================================
    bench_data = _fetch_benchmark_returns(benchmark, start, end, recorded)
    sse_data = _fetch_index_returns("sh000001", start, end, recorded)

    # ============================================================
    # Drawdown series
    # ============================================================
    drawdown_data = []
    if cum_return_data:
        peak = cum_return_data[0]["value"]
        for d in cum_return_data:
            if d["value"] > peak:
                peak = d["value"]
            dd = round(d["value"] - peak, 3)
            drawdown_data.append({"time": d["time"], "value": dd})

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
            f'<td>{t["date"]}</td>'
            f'<td style="color:{action_color};font-weight:bold">{action_text}</td>'
            f'<td>{t["security"]}</td>'
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
        trade_map[d].append(f"{action_text} {t['security']} {t['amount']}股 @{t['price']:.3f}")

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
                    op_parts.append(f'<span style="color:{op_color}">{o}</span>')
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
                    f'<li><b>{sec}</b>: {pos.amount} 股, 均价={pos.avg_cost:.3f}</li>'
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
    # Technical summary stats
    # ============================================================
    tech_stats = {}
    if not df.empty:
        df_s = df.sort_index()
        c = df_s["close"].iloc[-1]
        ma5_last = df_s["close"].rolling(5).mean().iloc[-1]
        ma20_last = df_s["close"].rolling(20).mean().iloc[-1]
        ma60_last = df_s["close"].rolling(60).mean().dropna()
        ma60_v = round(float(ma60_last.iloc[-1]), 3) if len(ma60_last) > 0 else None
        atr14 = _compute_atr(df_s["high"], df_s["low"], df_s["close"], 14)
        vol20 = df_s["volume"].rolling(20).mean().iloc[-1]
        vol_ratio = round(float(df_s["volume"].iloc[-1] / vol20), 2) if vol20 > 0 else None

        tech_stats = {
            "latest_price": round(c, 3),
            "ma5": round(float(ma5_last), 3),
            "ma20": round(float(ma20_last), 3),
            "ma60": ma60_v,
            "atr14": round(float(atr14), 3) if atr14 else None,
            "vol_ratio": vol_ratio,
            "period_high": round(float(df_s["high"].max()), 3),
            "period_low": round(float(df_s["low"].min()), 3),
        }

    # ============================================================
    # Build HTML
    # ============================================================
    bench_code = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    bench_label = {"000300": "沪深300", "000001": "上证指数"}.get(bench_code, bench_code)
    pnl_badge_class = "pos" if pnl >= 0 else "neg"

    html = _HTML_TEMPLATE.format(
        symbol=symbol,
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
        cum_return_json=json.dumps(cum_return_data),
        csi300_json=json.dumps(bench_data),
        sse_json=json.dumps(sse_data),
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
    )

    with open(out_path, "w") as f:
        f.write(html)

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
        "profit_loss_ratio": f"{analytics.get('profit_loss_ratio', 0):.2f}",
        "win_count": str(analytics.get("win_count", 0)),
        "loss_count": str(analytics.get("loss_count", 0)),
        "ann_vol": f"{analytics['annual_volatility']:.2%}",
        "bm_vol": f"{analytics.get('benchmark_volatility', 0):.2%}",
        "trade_count": str(analytics.get("trade_count", 0)),
        # For benchmark return chart (configured benchmark cumulative return %)
        "bench_last": f"{bench_data[-1]['value'] if bench_data else 0:.2f}",
    }


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测报告 · {symbol}</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<script>
if (typeof LightweightCharts === 'undefined') {{
  var s = document.createElement('script');
  s.src = 'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
  document.head.appendChild(s);
}}
</script>
<style>
  :root {{
    --bg: #f0f2f5; --card: #fff; --border: #e8e8e8;
    --text: #262626; --text-secondary: #595959; --text-dim: #8c8c8c;
    --primary: #1890ff; --green: #f5222d; --red: #52c41a; --yellow: #faad14;
    --green-bg: rgba(245,34,45,.06); --red-bg: rgba(82,196,26,.06);
    --shadow: 0 1px 4px rgba(0,0,0,.08);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); font-size: 13px; line-height: 1.5;
  }}
  /* Header */
  .header {{
    background: #fff; border-bottom: 1px solid var(--border);
    padding: 12px 0; box-shadow: var(--shadow);
  }}
  .header-inner {{
    max-width: 98vw; margin: 0 auto; padding: 0 16px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  h1 {{ font-size: 16px; font-weight: 600; color: var(--text); }}
  h1 .sym {{ color: var(--primary); }}
  .header-meta {{ font-size: 11px; color: var(--text-dim); margin-top: 2px; }}
  .pnl-badge {{
    padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 600;
  }}
  .pnl-badge.pos {{ background: var(--green-bg); color: var(--green); }}
  .pnl-badge.neg {{ background: var(--red-bg); color: var(--red); }}
  /* Container */
  .container {{ max-width: 98vw; margin: 0 auto; padding: 12px 16px 48px; }}
  /* Summary cards (like JoinQuant) */
  .summary {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px; margin-bottom: 12px;
  }}
  .card {{
    background: var(--card); border-radius: 4px; padding: 12px;
    box-shadow: var(--shadow); text-align: center;
  }}
  .card .label {{ font-size: 11px; color: var(--text-dim); margin-bottom: 6px; }}
  .card .value {{ font-size: 18px; font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }}
  /* Metric row (JoinQuant style) */
  .metric-row {{
    display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 12px;
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    overflow: hidden;
  }}
  .metric-item {{
    flex: 1; min-width: 100px; padding: 12px 8px;
    border-right: 1px solid var(--border); text-align: center;
    cursor: pointer; transition: background .15s;
  }}
  .metric-item:last-child {{ border-right: none; }}
  .metric-item:hover {{ background: #fafafa; }}
  .metric-item .m-label {{
    font-size: 11px; color: var(--text-dim); margin-bottom: 4px;
    display: flex; align-items: center; justify-content: center; gap: 4px;
  }}
  .metric-item .m-label svg {{ width: 12px; height: 12px; fill: currentColor; }}
  .metric-item .m-value {{
    font-size: 16px; font-weight: 600; color: var(--text);
    font-variant-numeric: tabular-nums;
  }}
  .metric-item .m-value.pos {{ color: var(--green); }}
  .metric-item .m-value.neg {{ color: var(--red); }}
  .metric-item .m-sub {{
    font-size: 10px; color: var(--text-dim); margin-top: 2px;
  }}
  /* Section title */
  .section-title {{
    font-size: 13px; font-weight: 600; color: var(--text);
    padding: 8px 0 6px; border-bottom: 1px solid var(--border); margin-bottom: 8px;
  }}
  /* Metric cards (used by both primary and secondary grids) */
  .metrics-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0; margin-bottom: 12px;
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    overflow: hidden;
  }}
  .metric-card {{
    padding: 10px 8px; text-align: center;
    border-right: 1px solid var(--border); cursor: pointer;
    transition: background .15s;
  }}
  .metric-card:last-child {{ border-right: none; }}
  .metric-card:hover {{ background: #fafafa; }}
  .metric-card .title-row {{
    display: flex; align-items: center; justify-content: center; gap: 3px;
    margin-bottom: 4px;
  }}
  .metric-card .mc-title {{
    font-size: 10px; color: var(--text-dim); font-weight: 500;
  }}
  .mc-info {{ display: none; }}  /* hide the 'i' badge in light theme */
  .metric-card .mc-val {{
    font-size: 16px; font-weight: 600; color: var(--text);
    font-variant-numeric: tabular-nums;
  }}
  .metric-card .mc-val.pos {{ color: var(--green); }}
  .metric-card .mc-val.neg {{ color: var(--red); }}
  .mc-grade-row {{ margin-top: 3px; min-height: 14px; }}
  .mc-grade {{
    display: inline-block; font-size: 9px; font-weight: 500;
    padding: 1px 4px; border-radius: 2px;
  }}
  .grade-excellent {{ background: rgba(245,34,45,.08); color: var(--green); }}
  .grade-good      {{ background: rgba(24,144,255,.08); color: var(--primary); }}
  .grade-fair      {{ background: rgba(250,173,20,.08); color: var(--yellow); }}
  .grade-poor      {{ background: rgba(82,196,26,.08);  color: #7cb342; }}
  /* Secondary metrics grid (responsive) */
  .metrics-grid-secondary {{
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  }}
  /* Chart panels */
  .chart-panel {{
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    margin-bottom: 8px; overflow: hidden;
  }}
  .chart-panel-head {{
    padding: 8px 16px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }}
  .chart-panel-head h2 {{ font-size: 13px; font-weight: 600; color: var(--text); }}
  .chart-tabs {{ display: flex; gap: 0; }}
  .chart-tab {{
    padding: 3px 10px; font-size: 11px; color: var(--text-dim);
    cursor: pointer; border: 1px solid var(--border); border-radius: 3px;
    margin-left: -1px; transition: all .15s;
  }}
  .chart-tab.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
  .chart-tab:hover:not(.active) {{ background: #fafafa; }}
  .chart-body {{ padding: 0; }}
  .chart-body .desc {{
    padding: 6px 16px; font-size: 11px; color: var(--text-dim);
    border-bottom: 1px solid var(--border);
  }}
  #kline    {{ width: 100%; height: 480px; }}
  #returns  {{ width: 100%; height: 300px; }}
  #drawdown {{ width: 100%; height: 160px; }}
  #pnlbar   {{ width: 100%; height: 160px; }}
  #dailyret {{ width: 100%; height: 160px; }}
  /* Legend */
  .legend {{ display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); align-items: center; }}
  .legend span {{ display: flex; align-items: center; gap: 4px; }}
  .legend .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
  .legend .ln {{ width: 16px; height: 2px; display: inline-block; }}
  /* Trade table */
  .trade-section {{
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    margin-bottom: 16px;
  }}
  .trade-section .tabs {{
    display: flex; border-bottom: 1px solid var(--border); padding: 0 16px;
  }}
  .trade-section .tab {{
    padding: 10px 16px; font-size: 13px; color: var(--text-dim);
    cursor: pointer; border-bottom: 2px solid transparent;
  }}
  .trade-section .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
  .trade-section .content {{ padding: 16px; }}
  /* Generic section */
  .section {{
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    padding: 16px; margin-bottom: 16px;
  }}
  .section .section-title {{ padding: 0; margin-bottom: 12px; }}
  .tab-bar {{ display: flex; border-bottom: 1px solid var(--border); margin-bottom: 12px; }}
  .tab {{
    padding: 10px 16px; font-size: 13px; color: var(--text-dim);
    cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s;
  }}
  .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .trade-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .trade-table th {{
    text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-weight: 500; font-size: 12px;
  }}
  .trade-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
  .trade-table tr:hover td {{ background: #fafafa; }}
  .cal-wrapper {{ max-height: 400px; overflow-y: auto; }}
  .cal-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .cal-table th {{
    text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-weight: 500; font-size: 12px; position: sticky; top: 0;
    background: var(--card); z-index: 1;
  }}
  .cal-table td {{ padding: 6px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; font-size: 12px; }}
  .positions ul {{ list-style: none; padding: 0; }}
  .positions li {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
  .positions li:last-child {{ border-bottom: none; }}
  .trade-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .trade-table th {{
    text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-weight: 500; font-size: 12px;
  }}
  .trade-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
  .trade-table tr:hover td {{ background: #fafafa; }}
  /* Positions */
  .positions {{
    background: var(--card); border-radius: 4px; box-shadow: var(--shadow);
    padding: 16px; margin-bottom: 16px;
  }}
  .positions h3 {{ font-size: 14px; font-weight: 600; margin-bottom: 12px; }}
  .positions ul {{ list-style: none; }}
  .positions li {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
  .positions li:last-child {{ border-bottom: none; }}
  /* Modal */
  .modal-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,.45);
    z-index: 2000; display: flex; align-items: center; justify-content: center;
    opacity: 0; pointer-events: none; transition: opacity .2s;
  }}
  .modal-overlay.open {{ opacity: 1; pointer-events: all; }}
  .modal {{
    background: #fff; border-radius: 8px; padding: 24px;
    max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 8px 32px rgba(0,0,0,.15); position: relative;
  }}
  .modal-close {{
    position: absolute; top: 12px; right: 12px; background: none; border: none;
    color: var(--text-dim); font-size: 20px; cursor: pointer;
  }}
  .modal h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; padding-right: 24px; }}
  .modal-cur {{ font-size: 28px; font-weight: 600; color: var(--primary); margin-bottom: 16px; }}
  .modal-sec {{ margin-bottom: 12px; }}
  .modal-sec h4 {{ font-size: 12px; color: var(--text-dim); font-weight: 500; margin-bottom: 4px; }}
  .modal-sec p {{ font-size: 13px; color: var(--text-secondary); line-height: 1.7; }}
  .modal-formula {{
    font-family: "SF Mono", monospace; font-size: 12px; background: #f5f5f5;
    padding: 8px 12px; border-radius: 4px; color: var(--text);
  }}
  .modal-ref {{ font-size: 11px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 8px; margin-top: 8px; }}
  /* Footer */
  .footer {{
    text-align: center; padding: 16px 0; color: var(--text-dim);
    font-size: 12px; border-top: 1px solid var(--border); margin-top: 16px;
  }}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}
  /* Tech stats grid */
  .tech-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 8px; margin-bottom: 12px;
  }}
  .tech-card {{
    background: #f5f5f5; border-radius: 4px; padding: 10px 12px; text-align: center;
  }}
  .tech-card .title {{ font-size: 11px; color: var(--text-dim); margin-bottom: 4px; }}
  .tech-card .val {{ font-size: 16px; font-weight: 600; color: var(--text); }}
  /* Source cards */
  .sources-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 12px;
  }}
  .src-card {{
    background: #f5f5f5; border-radius: 4px; padding: 14px; border-left: 3px solid var(--primary);
  }}
  .src-card .src-type {{ font-size: 10px; color: var(--primary); font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }}
  .src-card .src-name {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
  .src-card .src-desc {{ font-size: 12px; color: var(--text-secondary); line-height: 1.5; }}
  .src-card code {{ background: #e8e8e8; padding: 1px 4px; border-radius: 2px; font-size: 12px; }}
  /* Method list */
  .method-list {{ padding-left: 18px; font-size: 13px; color: var(--text-secondary); line-height: 1.8; }}
  .method-list li {{ margin-bottom: 6px; }}
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
    <div>
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

  <!-- Summary cards -->
  <div class="summary">
    <div class="card"><div class="label">初始资金</div><div class="value">&yen;{initial_capital}</div></div>
    <div class="card"><div class="label">期末净值</div><div class="value">&yen;{final_value}</div></div>
    <div class="card"><div class="label">总盈亏</div><div class="value" style="color:{pnl_color}">{pnl}</div></div>
    <div class="card"><div class="label">总收益率</div><div class="value" style="color:{pnl_color}">{pnl_pct}</div></div>
    <div class="card"><div class="label">买入次数</div><div class="value">{buy_count}</div></div>
    <div class="card"><div class="label">卖出次数</div><div class="value">{sell_count}</div></div>
  </div>

  <!-- Performance metrics -->
  <div class="section-title">绩效指标 <span style="opacity:.45;font-weight:400;font-size:10px">— 点击任意指标卡片可查看定义与解读</span></div>
  <div class="metrics-grid">
    <div class="metric-card" onclick="showMetric('ann_ret')">
      <div class="title-row"><span class="mc-title">年化收益率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-ann_ret">{ann_ret}</div>
      <div class="mc-grade-row"><div id="grade-ann_ret"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('excess_return')">
      <div class="title-row"><span class="mc-title">超额收益</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-excess_return">{excess_return}</div>
      <div class="mc-grade-row"><div id="grade-excess_return"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('bm_ret')">
      <div class="title-row"><span class="mc-title">{benchmark_name} 收益</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-bm_ret">{benchmark_ret}</div>
      <div class="mc-grade-row"><div id="grade-bm_ret"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('alpha')">
      <div class="title-row"><span class="mc-title">Alpha（超额收益）</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-alpha">{alpha}</div>
      <div class="mc-grade-row"><div id="grade-alpha"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('beta')">
      <div class="title-row"><span class="mc-title">Beta（市场敏感度）</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-beta">{beta}</div>
      <div class="mc-grade-row"><div id="grade-beta"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('sharpe')">
      <div class="title-row"><span class="mc-title">Sharpe 比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-sharpe">{sharpe}</div>
      <div class="mc-grade-row"><div id="grade-sharpe"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('win_rate')">
      <div class="title-row"><span class="mc-title">胜率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-win_rate">{win_rate}</div>
      <div class="mc-grade-row"><div id="grade-win_rate"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('profit_loss_ratio')">
      <div class="title-row"><span class="mc-title">盈亏比</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-profit_loss_ratio">{profit_loss_ratio}</div>
      <div class="mc-grade-row"><div id="grade-profit_loss_ratio"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('max_dd')">
      <div class="title-row"><span class="mc-title">最大回撤</span><span class="mc-info">i</span></div>
      <div class="mc-val neg" id="mv-max_dd">{max_dd}</div>
      <div class="mc-grade-row"><div id="grade-max_dd"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('sortino')">
      <div class="title-row"><span class="mc-title">Sortino 比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-sortino">{sortino}</div>
      <div class="mc-grade-row"><div id="grade-sortino"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('calmar')">
      <div class="title-row"><span class="mc-title">Calmar 比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-calmar">{calmar}</div>
      <div class="mc-grade-row"><div id="grade-calmar"></div></div>
    </div>
  </div>

  <!-- Secondary metrics row -->
  <div class="section-title">超额与风险详情</div>
  <div class="metrics-grid metrics-grid-secondary">
    <div class="metric-card" onclick="showMetric('daily_excess')">
      <div class="title-row"><span class="mc-title">日均超额收益</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-daily_excess">{daily_excess}</div>
      <div class="mc-grade-row"><div id="grade-daily_excess"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('excess_max_dd')">
      <div class="title-row"><span class="mc-title">超额收益最大回撤</span><span class="mc-info">i</span></div>
      <div class="mc-val neg" id="mv-excess_max_dd">{excess_max_dd}</div>
      <div class="mc-grade-row"><div id="grade-excess_max_dd"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('excess_sharpe')">
      <div class="title-row"><span class="mc-title">超额收益夏普比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-excess_sharpe">{excess_sharpe}</div>
      <div class="mc-grade-row"><div id="grade-excess_sharpe"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('daily_win_rate')">
      <div class="title-row"><span class="mc-title">日胜率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-daily_win_rate">{daily_win_rate}</div>
      <div class="mc-grade-row"><div id="grade-daily_win_rate"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('win_count')">
      <div class="title-row"><span class="mc-title">盈利次数</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-win_count">{win_count}</div>
      <div class="mc-grade-row"><div id="grade-win_count"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('loss_count')">
      <div class="title-row"><span class="mc-title">亏损次数</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-loss_count">{loss_count}</div>
      <div class="mc-grade-row"><div id="grade-loss_count"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('info_ratio')">
      <div class="title-row"><span class="mc-title">信息比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-info_ratio">{info_ratio}</div>
      <div class="mc-grade-row"><div id="grade-info_ratio"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('ann_vol')">
      <div class="title-row"><span class="mc-title">策略波动率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-ann_vol">{ann_vol}</div>
      <div class="mc-grade-row"><div id="grade-ann_vol"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('bm_vol')">
      <div class="title-row"><span class="mc-title">基准波动率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-bm_vol">{bm_vol}</div>
      <div class="mc-grade-row"><div id="grade-bm_vol"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('trade_count')">
      <div class="title-row"><span class="mc-title">交易次数</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-trade_count">{trade_count}</div>
      <div class="mc-grade-row"><div id="grade-trade_count"></div></div>
    </div>
  </div>

  <!-- Technical stats (populated by JS) -->
  <div id="tech-section" style="display:none">
    <div class="section-title">技术指标</div>
    <div class="tech-grid" id="tech-stats"></div>
    <p class="chart-source" style="margin-bottom:14px">
      数据来源：AKShare（东方财富行情接口）&middot; 含 MA、ATR(14)、量比等指标，基于回测期间的前复权日线数据计算。
    </p>
  </div>

  <!-- K-line chart -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <div>
        <h2>K 线图 &middot; 技术指标</h2>
        <div class="chart-desc">日 K 线含 MA5/MA20/MA60 均线、20日动态支撑/压力位、成交量柱，以及买卖信号标记。<span style="color:var(--primary);font-weight:500">&middot; 使用前复权价格（含分红调整）</span></div>
      </div>
      <div class="legend">
        <span><span class="dot" style="background:#f5222d"></span>MA5</span>
        <span><span class="dot" style="background:#1890ff"></span>MA20</span>
        <span><span class="dot" style="background:#722ed1"></span>MA60</span>
        <span><span class="dot" style="background:#f5222d"></span>买入</span>
        <span><span class="dot" style="background:#52c41a"></span>卖出</span>
      </div>
    </div>
    <div id="kline"></div>
  </div>

  <!-- Cumulative returns comparison -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>累计收益率</h2>
      <div class="chart-tabs" id="retTabs">
        <span class="chart-tab active" data-series="all" onclick="toggleReturnSeries('all',this)">策略+基准</span>
        <span class="chart-tab" data-series="excess" onclick="toggleReturnSeries('excess',this)">超额收益</span>
        <span class="chart-tab" data-series="strategy" onclick="toggleReturnSeries('strategy',this)">仅策略</span>
        <span class="chart-tab" data-series="benchmark" onclick="toggleReturnSeries('benchmark',this)">仅基准</span>
      </div>
    </div>
    <div class="chart-body">
      <div class="desc">策略与{benchmark_name}在相同区间的累计收益率（%）横向对比，直观评估策略 Alpha 来源。</div>
    </div>
    <div id="returns"></div>
    <div class="legend" style="padding: 8px 16px;">
      <span><span class="ln" style="background:#f5222d"></span>策略</span>
      <span><span class="ln" style="background:#1890ff"></span>{benchmark_name}</span>
    </div>
  </div>

  <!-- Drawdown -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>回撤曲线</h2>
    </div>
    <div class="chart-body">
      <div class="desc">策略净值相较历史峰值的累计回撤（%）。红色区域越深代表风险越大。</div>
    </div>
    <div id="drawdown"></div>
  </div>

  <!-- Daily P&L -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>每日盈亏</h2>
    </div>
    <div class="chart-body">
      <div class="desc">每个交易日的资产净值变动额（元）。可直观观察收益分布形态与连续亏损风险。</div>
    </div>
    <div id="pnlbar"></div>
  </div>

  <!-- Daily returns -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <h2>每日收益率</h2>
    </div>
    <div class="chart-body">
      <div class="desc">日度收益率分布，用于观察策略波动性及收益连续性。</div>
    </div>
    <div id="dailyret"></div>
  </div>

  <!-- Trade details & calendar -->
  <div class="section">
    <div class="section-title">交易明细与日历</div>
    <div class="tab-bar">
      <div class="tab active" data-tab="tb-trades">交易明细</div>
      <div class="tab" data-tab="tb-calendar">交易日历</div>
      <div class="tab" data-tab="tb-positions">当前持仓</div>
    </div>
    <div id="tb-trades" class="tab-content active">
      <table class="trade-table">
        <thead><tr>
          <th>#</th><th>日期</th><th>操作</th><th>代码</th>
          <th>价格</th><th>数量</th><th>手续费</th>
        </tr></thead>
        <tbody>{trade_rows}</tbody>
      </table>
    </div>
    <div id="tb-calendar" class="tab-content">
      <div class="cal-wrapper">
        <table class="cal-table">
          <thead><tr>
            <th>日期</th><th>累计收益</th><th>回撤</th><th>操作</th>
          </tr></thead>
          <tbody>{calendar_rows}</tbody>
        </table>
      </div>
    </div>
    <div id="tb-positions" class="tab-content">
      <ul>{positions_html}</ul>
    </div>
  </div>

  <!-- Data sources & methodology -->
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
          <div class="src-desc">A股日线 OHLCV 行情通过 <code>stock_zh_a_hist</code> 获取，<strong>前复权（qfq）</strong>处理。前复权已将历史分红纳入价格调整，回测收益已反映分红影响。数据由东方财富网提供，仅供研究使用。</div>
        </div>
        <div class="src-card">
          <div class="src-type">基准指数</div>
          <div class="src-name">沪深300（000300）&middot; 上证综指（000001）</div>
          <div class="src-desc">通过 AKShare <code>stock_zh_index_daily_em</code> 获取，以回测起始日收盘价归一化后与策略区间对齐。</div>
        </div>
        <div class="src-card">
          <div class="src-type">无风险利率</div>
          <div class="src-name">固定 3.0% / 年</div>
          <div class="src-desc">参考近年中国国债市场平均利率水平，用于 Sharpe、Sortino、Alpha 等超额收益指标的计算（日化 = 3% &divide; 252）。</div>
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
        <li><strong>年化收益率</strong>(1 + 总收益率)^(252/N) &minus; 1，N 为回测交易日数，每年按 252 个交易日折算。</li>
        <li><strong>Sharpe 比率</strong>(日均收益率 &minus; r_f/252) / 日收益率标准差 &times; &radic;252。参考：Sharpe (1966, 1994)。</li>
        <li><strong>Sortino 比率</strong>同 Sharpe 但分母仅用下行波动率（仅负收益标准差）。参考：Sortino &amp; Price (1994)。</li>
        <li><strong>最大回撤</strong>max[(峰值 &minus; 谷值) / 峰值]，反映策略可能面临的最大历史亏损幅度。</li>
        <li><strong>Calmar 比率</strong>年化收益率 / |最大回撤|，衡量单位回撤的年化回报。参考：Young (1991)。</li>
        <li><strong>Alpha / Beta</strong>基于 CAPM，以沪深300为市场基准。&beta; = Cov(R_p,R_m)/Var(R_m)；&alpha; = R_p &minus; [r_f + &beta;(R_m &minus; r_f)]（均年化）。参考：Sharpe (1964)，Lintner (1965)。</li>
        <li><strong>胜率</strong>按先进先出（FIFO）配对买卖，盈利对数 / 全部配对数。注意需结合盈亏比综合评估。</li>
        <li><strong>ATR(14)</strong>14日平均真实波幅，反映近期价格波动区间均值。参考：Wilder (1978)。</li>
        <li><strong>支撑/压力位</strong>20日滚动最低/最高价计算，动态非静态水平线。</li>
        <li><strong>量比</strong>当日成交量 / 近20日成交量均值，&gt;2 通常视为明显放量信号。</li>
      </ul>
    </div>
  </div>

</div>

<div class="footer">
  EasyQuant &middot; eqlib &nbsp;|&nbsp;
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
      desc: '将回测期间的累计总收益率换算为年化水平，便于与其他资产或指数横向比较。N 为实际回测交易日数（约252个交易日/年）。',
      interp: '数值越高越好。>15% 为优秀，>8% 为良好，>0% 为正收益，≤0% 为亏损。注意短期高收益不代表长期稳定性。',
      ref: '标准年化换算公式（Geometric Mean Return Annualization），金融分析行业通用。',
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
      desc: '衡量每单位总风险（年化波动率）所获得的超额年化收益。R_p 为策略日收益，r_f 为无风险利率日化值（年化3%÷252），σ_p 为日收益率标准差，公式最终年化。',
      interp: '>2.0 优秀，>1.0 良好，>0.5 一般，≤0.5 较差，负值表示不如无风险资产。',
      ref: 'Sharpe, W.F. (1966). Mutual Fund Performance. Journal of Business, 39(1), 119–138.\\nSharpe, W.F. (1994). The Sharpe Ratio. Journal of Portfolio Management.',
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
      desc: '与 Sharpe 类似，但分母仅计算下行波动率（仅负收益的标准差），对上行收益的波动不作惩罚，更真实反映投资者面临的实际风险。',
      interp: '>2.0 优秀，>1.0 良好。通常高于 Sharpe；若明显低于 Sharpe，说明策略亏损时波动较大。',
      ref: 'Sortino, F.A. & Price, L.N. (1994). Performance Measurement in a Downside Risk Framework. Journal of Investing, 3(3), 59–64.',
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
      desc: '在整个回测期间，净值从历史最高点到随后最低点的最大跌幅百分比。代表持有该策略可能遭遇的最坏亏损情形，是风险控制的核心指标。',
      interp: '<5% 优秀，<10% 良好，<20% 可接受，>20% 风险偏高。A股高波动性背景下 <15% 被视为良好控制。',
      ref: 'Magdon-Ismail, M. & Atiya, A. (2004). Maximum Drawdown. Risk Magazine, 17(10), 99–102.',
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
      desc: '以先进先出（FIFO）方式配对每笔买卖，统计卖出价格高于对应买入价格的比例。注意：高胜率 ≠ 高盈利，还需结合盈亏比（赔率）综合评估策略质量。',
      interp: '>60% 优秀，>50% 良好，40–50% 一般，<40% 需结合盈亏比判断策略合理性。',
      ref: 'Van Tharp (1999). Trade Your Way to Financial Freedom. McGraw-Hill.',
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
      name: 'Alpha（超额收益）',
      formula: 'α = R_p(年化) − [r_f + β × (R_m(年化) − r_f)]',
      desc: '基于 CAPM 模型，衡量策略在承担系统性市场风险（β）之外额外获得的年化超额收益。正 Alpha 表明策略相对基准创造了独立附加价值。',
      interp: '>5% 优秀，>0% 说明策略相对基准有价值，<0% 表示风险调整后跑输基准，<-5% 则显著落后。',
      ref: 'Jensen, M.C. (1968). The Performance of Mutual Funds in the Period 1945-1964. Journal of Finance, 23(2), 389–416.\\nCAPM: Sharpe (1964), Lintner (1965), Mossin (1966).',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 5)  return ['excellent', '优秀 >5%'];
        if (n > 0)  return ['good',      '正 Alpha'];
        if (n > -5) return ['fair',      '略低 > −5%'];
        return ['poor', '负 Alpha'];
      }},
    }},
    beta: {{
      name: 'Beta（市场敏感度）',
      formula: 'β = Cov(R_p, R_m) / Var(R_m)',
      desc: '衡量策略收益率相对于市场基准（沪深300）变动的敏感程度。β=1 与市场同步；β>1 放大市场波动（进取型）；β<1 减弱市场波动（防御型）；β<0 与市场反向。',
      interp: '无绝对好坏，取决于策略目标。低波动/防御型：β<0.8；进取型：β>1.2；套利对冲型：β≈0。',
      ref: 'CAPM: Sharpe, W.F. (1964). Capital Asset Prices: A Theory of Market Equilibrium. Journal of Finance, 19(3), 425–442.',
      grader(v) {{ return null; }},
    }},
    bm_ret: {{
      name: '{benchmark_name} 收益（基准参考）',
      formula: '(期末收盘价 / 期初收盘价 − 1) × 100%',
      desc: '沪深300指数在相同回测区间内的累计涨跌幅，作为评估策略主动收益（Alpha）的参照基准。沪深300由沪深两市市值最大的300只A股构成，覆盖约70%的A股总市值。',
      interp: '将策略收益率与基准对比：策略超越基准则产生正的主动收益；低于基准则为负的主动收益。基准本身的高低不影响策略评价，关键看相对表现。',
      ref: '沪深300指数（000300.SH），2005年4月8日发布，基日2004年12月31日=1000点，由中证指数有限公司编制。',
      grader(v) {{ return null; }},
    }},
    excess_return: {{
      name: '超额收益',
      formula: '策略总收益率 − 基准总收益率',
      desc: '策略相对基准指数在相同区间的绝对超额回报。正值表示跑赢基准，负值表示跑输。是最直观的策略附加值指标。',
      interp: '>10% 优秀，>0% 正超额，<0% 跑输基准。注意需结合风险水平判断超额是否值得承担。',
      ref: 'Active Return = R_p − R_b，现代投资组合理论通用。',
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
      desc: '衡量策略年化回报相对最大回撤的性价比。与 Sharpe 类似，但分母用最大回撤而非波动率，更侧重下行风险。',
      interp: '>1.0 优秀，>0.5 良好，<0.3 偏低。越高说明单位回撤带来的年化收益越大。',
      ref: 'Young, T.W. (1991). CALMAR Ratio: A Smarter Way to Track Performance. Managed Account Reports.',
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
      formula: '平均单笔盈利金额 / 平均单笔亏损金额',
      desc: '衡量每笔交易平均赚多少与赔多少的比率。与胜率配合使用：高盈亏比+中等胜率往往优于低盈亏比+高胜率。',
      interp: '>3:1 优秀，>2:1 良好，>1:1 盈利覆盖亏损，<1:1 每笔亏损大于盈利。盈亏比×胜率>1 为盈利系统的必要条件。',
      ref: 'Van Tharp (1999). Trade Your Way to Financial Freedom. McGraw-Hill.',
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
      desc: '策略每日相对基准的超额收益的均值年化值。反映策略平均每天能创造多少超额年化回报。',
      interp: '>3% 优秀，>0% 日均正超额，<0% 日均跑输基准。',
      ref: 'Daily Active Return annualized，行业通用。',
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
      formula: 'max[(超额累积峰值 − 超额累积谷值) / 超额累积峰值]',
      desc: '超额收益累积曲线的最大回撤。即使策略整体盈利，超额回撤过大说明策略相对基准存在阶段性显著落后。',
      interp: '<5% 优秀，<10% 良好，>15% 说明策略有较长时间大幅跑输基准。',
      ref: 'Tracking Error Drawdown，机构投资风控常用指标。',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n < 5)  return ['excellent', '优秀 <5%'];
        if (n < 10) return ['good',      '良好 <10%'];
        if (n < 15) return ['fair',      '可接受 <15%'];
        return ['poor', '偏高 >15%'];
      }},
    }},
    excess_sharpe: {{
      name: '超额收益夏普比率',
      formula: '(E[超额日收益] − r_f) / σ(超额日收益) × √252',
      desc: '以超额日收益（策略 − 基准）为输入计算的 Sharpe 比率。衡量每单位超额波动所获得的风险调整后回报。',
      interp: '>1.0 优秀，>0.5 良好，>0 正超额收益经风险调整后仍为正值。',
      ref: 'Information Ratio 的变体，行业通用。',
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
      desc: '策略在多少个交易日的日度收益为正。反映策略的每日稳定性，与交易胜率（配对买卖）意义不同。',
      interp: '>55% 优秀，>50% 良好，<45% 偏弱。日胜率通常高于交易胜率，因为长期趋势向上的策略仍有大量震荡日。',
      ref: 'Daily Hit Ratio，行业通用。',
      grader(v) {{
        const n = parseFloat(v);
        if (isNaN(n)) return null;
        if (n > 55) return ['excellent', '优秀 >55%'];
        if (n > 50) return ['good',      '良好 >50%'];
        return ['fair', '一般'];
      }},
    }},
    win_count: {{
      name: '盈利次数',
      formula: 'FIFO配对中盈利交易的对数',
      desc: '回测期间完成的配对交易中，卖出价高于平均买入成本的次数。',
      interp: '绝对数值，需与亏损次数结合观察。次数越多说明策略活跃度越高。',
      ref: 'Trade count，行业通用。',
      grader(v) {{ return null; }},
    }},
    loss_count: {{
      name: '亏损次数',
      formula: 'FIFO配对中亏损交易的对数',
      desc: '回测期间完成的配对交易中，卖出价低于平均买入成本的次数。',
      interp: '越少越好，但需结合盈亏比判断。少量大亏损可能比大量小亏损更致命。',
      ref: 'Trade count，行业通用。',
      grader(v) {{ return null; }},
    }},
    info_ratio: {{
      name: '信息比率',
      formula: 'mean(策略日收益 − 基准日收益) / std(策略日收益 − 基准日收益) × √252',
      desc: '衡量每单位跟踪误差所获得的主动年化收益。是主动管理和量化策略评估的核心指标之一。',
      interp: '>0.5 优秀，>0.3 良好，>0 正主动收益，<0 跑输基准。',
      ref: 'Grinold & Kahn (1999). Active Portfolio Management. McGraw-Hill.',
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
      name: '策略波动率',
      formula: 'σ(策略日收益) × √252',
      desc: '策略日收益率的年化标准差，衡量策略收益的总体波动水平。',
      interp: '<10% 低波动，10-20% 中等，20-30% 高波动，>30% 极高波动。低波动不等于低风险，还需看最大回撤。',
      ref: 'Annualized Volatility，行业通用。',
      grader(v) {{ return null; }},
    }},
    bm_vol: {{
      name: '基准波动率',
      formula: 'σ(基准日收益) × √252',
      desc: '基准指数日收益率的年化标准差，用于与策略波动率对比。A股基准波动率通常在 15-25% 之间。',
      interp: '与策略波动率对比：策略波动率低于基准说明策略更平稳；高于基准说明策略放大了波动。',
      ref: 'Annualized Volatility，行业通用。',
      grader(v) {{ return null; }},
    }},
    trade_count: {{
      name: '交易次数',
      formula: '完成的 FIFO 配对交易数量',
      desc: '回测期间完成的配对买卖总次数。反映策略的活跃度和信号频率。',
      interp: '过少可能信号过于严格或缺乏机会，过多可能增加交易成本。需结合盈亏比和胜率综合判断。',
      ref: 'Trade count，行业通用。',
      grader(v) {{ return null; }},
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
      gradeEl.innerHTML = `<span class="mc-grade grade-${{cls}}">${{label}}</span>`;
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
      body += `<div class="modal-sec"><h4>计算公式</h4><div class="modal-formula">${{def.formula}}</div></div>`;
    if (def.desc)
      body += `<div class="modal-sec"><h4>指标说明</h4><p>${{def.desc}}</p></div>`;
    if (def.interp)
      body += `<div class="modal-sec"><h4>解读指南</h4><p>${{def.interp}}</p></div>`;
    if (def.ref)
      body += `<div class="modal-ref">&#128218; 参考文献：${{def.ref}}</div>`;
    document.getElementById('md-body').innerHTML = body;
    document.getElementById('mdOverlay').classList.add('open');
  }}

  function closeModal() {{
    document.getElementById('mdOverlay').classList.remove('open');
  }}

  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

  /* =================================================================
     CHART COMMON OPTIONS
     ================================================================= */
  const cmn = {{
    layout: {{
      background: {{ type: 'solid', color: '#fff' }},
      textColor: '#8c8c8c', fontSize: 11,
      fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif',
    }},
    grid: {{ vertLines: {{ color: '#f5f5f5' }}, horzLines: {{ color: '#f5f5f5' }} }},
    timeScale: {{
      borderColor: '#e8e8e8',
      timeVisible: false,
      barSpacing: 6,
    }},
    rightPriceScale: {{ borderColor: '#e8e8e8' }},
    crosshair: {{
      mode: 1,
      vertLine: {{ color: '#d9d9d9', width: 1, style: 2, labelBackgroundColor: '#8c8c8c' }},
      horzLine: {{ color: '#d9d9d9', width: 1, style: 2, labelBackgroundColor: '#8c8c8c' }},
    }},
  }};

  /* =================================================================
     CHART INITIALIZATION
     ================================================================= */
  var chartError = false;
  try {{
    if (typeof LightweightCharts === 'undefined') {{
      throw new Error('LightweightCharts library not loaded from CDN');
    }}

    /* K-line */
    const kEl = document.getElementById('kline');
    const kChart = LightweightCharts.createChart(kEl, {{
      ...cmn, width: kEl.clientWidth, height: 480,
      rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.22 }} }},
    }});
    const cSeries = kChart.addCandlestickSeries({{
      upColor: '#f5222d', downColor: '#52c41a',
      borderUpColor: '#f5222d', borderDownColor: '#52c41a',
      wickUpColor: '#f5222d', wickDownColor: '#52c41a',
    }});
    cSeries.setData({candlestick_json});
    cSeries.setMarkers({markers_json});
    kChart.addLineSeries({{ color: '#f5222d', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma5_json});
    kChart.addLineSeries({{ color: '#1890ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma20_json});
    kChart.addLineSeries({{ color: '#722ed1', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma60_json});
    kChart.addLineSeries({{ color: 'rgba(82,196,26,0.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData({support_json});
    kChart.addLineSeries({{ color: 'rgba(245,34,45,0.55)',  lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData({resistance_json});
    const volS = kChart.addHistogramSeries({{
      priceFormat: {{ type: 'volume' }},
      priceScaleId: 'vol',
    }});
    volS.priceScale().applyOptions({{ scaleMargins: {{ top: 0.8, bottom: 0 }} }});
    volS.setData({volume_json});
    kChart.timeScale().fitContent();

    /* Cumulative returns — strategy + benchmark lines */
    const rEl = document.getElementById('returns');
    const rChart = LightweightCharts.createChart(rEl, {{ ...cmn, width: rEl.clientWidth, height: 300 }});
    const stratLine = rChart.addLineSeries({{
      color: '#f5222d', lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerVisible: true, title: '策略',
    }});
    stratLine.setData({cum_return_json});
    const benchLine = rChart.addLineSeries({{
      color: '#1890ff', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerVisible: true, title: '{benchmark_name}',
    }});
    benchLine.setData({csi300_json});

    /* Excess return line (computed client-side) */
    const excessLine = rChart.addLineSeries({{
      color: '#722ed1', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false, title: '超额收益',
    }});
    var excessReturnData = [];
    if ({cum_return_json}.length > 0 && {csi300_json}.length > 0) {{
      var cumArr = {cum_return_json};
      var benchArr = {csi300_json};
      var benchMap = {{}};
      benchArr.forEach(function(d) {{ benchMap[d.time] = d.value; }});
      cumArr.forEach(function(d) {{
        if (benchMap.hasOwnProperty(d.time)) {{
          excessReturnData.push({{ time: d.time, value: +(d.value - benchMap[d.time]).toFixed(3) }});
        }}
      }});
    }}
    excessLine.setData(excessReturnData);

    rChart.timeScale().fitContent();

    /* Toggle return series visibility */
    var returnSeriesVisible = {{ strat: true, bench: true, excess: false }};
    window.toggleReturnSeries = function(mode, el) {{
      // Update tab active state
      var tabs = document.querySelectorAll('#retTabs .chart-tab');
      tabs.forEach(function(t) {{ t.classList.remove('active'); }});
      if (el) el.classList.add('active');

      if (mode === 'all') {{
        returnSeriesVisible = {{ strat: true, bench: true, excess: false }};
      }} else if (mode === 'excess') {{
        returnSeriesVisible = {{ strat: true, bench: false, excess: true }};
      }} else if (mode === 'strategy') {{
        returnSeriesVisible = {{ strat: true, bench: false, excess: false }};
      }} else if (mode === 'benchmark') {{
        returnSeriesVisible = {{ strat: false, bench: true, excess: false }};
      }}
      stratLine.applyOptions({{ visible: returnSeriesVisible.strat }});
      benchLine.applyOptions({{ visible: returnSeriesVisible.bench }});
      excessLine.applyOptions({{ visible: returnSeriesVisible.excess }});
    }};

    /* Drawdown */
    const ddEl = document.getElementById('drawdown');
    const ddChart = LightweightCharts.createChart(ddEl, {{
      ...cmn, width: ddEl.clientWidth, height: 160,
      rightPriceScale: {{ scaleMargins: {{ top: 0.1, bottom: 0.05 }} }},
    }});
    const ddSeries = ddChart.addAreaSeries({{
      lineColor: '#52c41a', topColor: 'rgba(82,196,26,0.12)', bottomColor: 'rgba(82,196,26,0)',
      lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
    }});
    ddSeries.setData({drawdown_json});
    // Add zero line via a line series
    var ddZeroData = {drawdown_json}.length > 0 ? [{{ time: {drawdown_json}[0].time, value: 0 }}, {{ time: {drawdown_json}[{drawdown_json}.length - 1].time, value: 0 }}] : [];
    var ddZeroLine = ddChart.addLineSeries({{
      color: '#d9d9d9', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
    }});
    ddZeroLine.setData(ddZeroData);
    ddChart.timeScale().fitContent();

    /* Daily P&L */
    const pEl = document.getElementById('pnlbar');
    const pChart = LightweightCharts.createChart(pEl, {{ ...cmn, width: pEl.clientWidth, height: 160 }});
    // Build histogram with per-bar colors
    var pnlRaw = {pnl_bar_json};
    var pnlHistData = pnlRaw.map(function(d) {{
      return {{
        time: d.time,
        value: d.value,
        color: d.color || (d.value >= 0 ? '#f5222d' : '#52c41a'),
      }};
    }});
    pChart.addHistogramSeries({{
      priceFormat: {{ type: 'volume' }},
    }}).setData(pnlHistData);
    // Add zero line
    var pZeroData = pnlRaw.length > 0 ? [{{ time: pnlRaw[0].time, value: 0 }}, {{ time: pnlRaw[pnlRaw.length - 1].time, value: 0 }}] : [];
    pChart.addLineSeries({{
      color: '#d9d9d9', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
    }}).setData(pZeroData);
    pChart.timeScale().fitContent();

    /* Daily returns */
    const drEl = document.getElementById('dailyret');
    const drChart = LightweightCharts.createChart(drEl, {{ ...cmn, width: drEl.clientWidth, height: 160 }});
    var drRaw = {daily_returns_json};
    var drHistData = drRaw.map(function(d) {{
      return {{
        time: d.time,
        value: d.value,
        color: d.color || (d.value >= 0 ? '#f5222d' : '#52c41a'),
      }};
    }});
    drChart.addHistogramSeries({{
      priceFormat: {{ type: 'percent' }},
    }}).setData(drHistData);
    // Add zero line
    var drZeroData = drRaw.length > 0 ? [{{ time: drRaw[0].time, value: 0 }}, {{ time: drRaw[drRaw.length - 1].time, value: 0 }}] : [];
    drChart.addLineSeries({{
      color: '#d9d9d9', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
    }}).setData(drZeroData);
    drChart.timeScale().fitContent();

    /* Sync all time scales */
    const allCharts = [kChart, rChart, ddChart, pChart, drChart];
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
        [[kChart, kEl], [rChart, rEl], [ddChart, ddEl], [pChart, pEl], [drChart, drEl]]
          .forEach(([c, el]) => c.applyOptions({{ width: el.clientWidth }}));
      }}, 150);
    }});
  }} catch(e) {{
    chartError = true;
    console.error('Chart initialization error:', e);
    ['kline','returns','drawdown','pnlbar','dailyret'].forEach(function(id) {{
      var el = document.getElementById(id);
      if (el) {{
        el.style.display = 'flex';
        el.style.alignItems = 'center';
        el.style.justifyContent = 'center';
        el.style.background = '#fafafa';
        el.style.color = '#999';
        el.style.fontSize = '14px';
        el.innerHTML = '<div style="text-align:center;padding:40px"><div style="font-size:24px;margin-bottom:8px">&#9888;</div>' +
          '<div>' + e.message + '</div><div style="font-size:12px;margin-top:8px;color:#bbb">图表库加载失败，请检查网络连接</div></div>';
      }}
    }});
  }}

  /* Technical stats */
  const tech = {tech_json};
  if (Object.keys(tech).length > 0) {{
    document.getElementById('tech-section').style.display = '';
    const items = [
      ['最新价',   tech.latest_price],
      ['MA5',      tech.ma5],
      ['MA20',     tech.ma20],
      ['MA60',     tech.ma60],
      ['ATR(14)',  tech.atr14],
      ['量比',     tech.vol_ratio],
      ['期间最高', tech.period_high],
      ['期间最低', tech.period_low],
    ].filter(([, v]) => v !== null && v !== undefined);
    document.getElementById('tech-stats').innerHTML = items.map(([lbl, val]) =>
      `<div class="tech-card"><div class="title">${{lbl}}</div>` +
      `<div class="val">${{typeof val === 'number' ? val.toLocaleString() : val}}</div></div>`
    ).join('');
  }}

  /* Render grade badges */
  renderGrades();

  /* Tabs — works for both .section (trade tabs + data source tabs) and
     .trade-section (if used independently) */
  document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
      // Find the nearest container that holds tabs and tab-content
      const container = tab.closest('.section') || tab.closest('.trade-section');
      if (!container) return;
      container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add('active');
    }});
  }});

}})();
</script>
</body>
</html>"""



def generate_report_md(result, out_path):
    """Generate professional Markdown report with risk metrics,
    trade analysis, benchmark comparison, and per-stock breakdown.
    """
    from eqlib.attribution import analyze_returns, brinson_attribution, fama_french_analysis
    from eqlib.data import fetch_stock_data

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    analytics = analyze_returns(result)
    bench_data = {}
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_init = bench_df["close"].iloc[0]
            bench_final = bench_df["close"].iloc[-1]
            bench_ret = (bench_final - bench_init) / bench_init * 100
            bench_data["return"] = bench_ret
            bench_data["init"] = bench_init
            bench_data["final"] = bench_final
    except Exception:
        pass

    securities = set(t["security"] for t in trade_log)
    bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")

    lines = []
    # ============================================================
    # Header
    # ============================================================
    lines.append(f"# Backtest Report")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **Period** | {ctx.start_date} to {ctx.end_date} |")
    lines.append(f"| **Initial Capital** | {initial:,.2f} |")
    lines.append(f"| **Final Value** | {final:,.2f} |")
    lines.append(f"| **P&L** | {pnl:+,.2f} ({pnl_pct:+.2f}%) |")
    lines.append(f"| **Benchmark** | {bench_label} |")
    if bench_data:
        bench_str = f"+{bench_data['return']:.2f}%" if bench_data["return"] >= 0 else f"{bench_data['return']:.2f}%"
        lines.append(f"| **Benchmark Return** | {bench_str} |")
    lines.append("")

    # ============================================================
    # Risk Metrics
    # ============================================================
    if analytics:
        lines.append("## Risk Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Annual Return | {analytics['annual_return']:+.2%} |")
        lines.append(f"| Annual Volatility | {analytics['annual_volatility']:.2%} |")
        lines.append(f"| Sharpe Ratio | {analytics['sharpe_ratio']:.2f} |")
        lines.append(f"| Sortino Ratio | {analytics['sortino_ratio']:.2f} |")
        lines.append(f"| Max Drawdown | {analytics['max_drawdown']:.2%} |")
        if analytics.get("max_drawdown_start"):
            lines.append(f"| Max DD Period | {analytics['max_drawdown_start']} to {analytics['max_drawdown_end']} |")
        lines.append(f"| Calmar Ratio | {analytics['calmar_ratio']:.2f} |")
        lines.append(f"| Alpha (annual) | {analytics['alpha']:+.2%} |")
        lines.append(f"| Beta | {analytics['beta']:.2f} |")
        lines.append(f"| Information Ratio | {analytics['information_ratio']:.2f} |")
        lines.append(f"| Win Rate (daily) | {analytics['win_rate']:.1%} |")
        lines.append(f"| Trading Days | {analytics['trading_days']} |")
        lines.append("")

        # ── Excess Return Analysis ──────────────────────────────────────
        lines.append("## Excess Return Analysis")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Excess Return | {analytics.get('excess_return', 0):+.2%} |")
        lines.append(f"| Benchmark Return | {analytics.get('benchmark_return', 0):+.2%} |")
        lines.append(f"| Daily Avg Excess Return | {analytics.get('daily_excess_return', 0):+.4%} |")
        lines.append(f"| Excess Return Max Drawdown | {analytics.get('excess_return_max_drawdown', 0):.2%} |")
        lines.append(f"| Excess Return Sharpe | {analytics.get('excess_return_sharpe', 0):.2f} |")
        lines.append("")

        # ── Trade Statistics ────────────────────────────────────────────
        lines.append("## Trade Statistics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Win Rate (trade) | {analytics['win_rate_trade']:.1%} |")
        lines.append(f"| Win Count | {analytics.get('win_count', 0)} |")
        lines.append(f"| Loss Count | {analytics.get('loss_count', 0)} |")
        lines.append(f"| Profit/Loss Ratio | {analytics.get('profit_loss_ratio', 0):.2f} |")
        lines.append(f"| Trade Count | {analytics['trade_count']} |")
        lines.append(f"| Annual Turnover | {analytics['annual_turnover']:.2%} |")
        lines.append(f"| Total Commission | {analytics['total_commission']:,.2f} |")
        lines.append("")

    # ============================================================
    # Trade Summary
    # ============================================================
    buy_count = sum(1 for t in trade_log if t["type"] == "BUY")
    sell_count = sum(1 for t in trade_log if t["type"] == "SELL")
    total_commission = sum(t.get("commission", 0) for t in trade_log)
    lines.append("## Trade Summary")
    lines.append("")
    lines.append(f"- Buy orders: {buy_count}")
    lines.append(f"- Sell orders: {sell_count}")
    lines.append(f"- Total commission: {total_commission:,.2f}")
    lines.append(f"- Securities traded: {len(securities)}")
    lines.append("")

    # Per-trade P&L (pair buy/sell by security)
    if trade_log:
        lines.append("## Trade P&L")
        lines.append("")
        lines.append("| # | Security | Buy Date | Buy Price | Sell Date | Sell Price | P&L |")
        lines.append("|---|----------|----------|-----------|-----------|------------|-----|")

        trade_pairs: dict = {}  # sec -> list of buys
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
                pnl_str = f"+{trade_pnl:,.0f}" if trade_pnl >= 0 else f"{trade_pnl:,.0f}"
                trade_num += 1
                lines.append(
                    f"| {trade_num} | {sec} | {buy_t['date']} | {buy_t['price']:.3f} "
                    f"| {t['date']} | {t['price']:.3f} | {pnl_str} |"
                )

        # Open positions (unmatched buys)
        for sec, buys in trade_pairs.items():
            for buy_t in buys:
                lines.append(
                    f"| - | {sec} | {buy_t['date']} | {buy_t['price']:.3f} "
                    f"| — open — | — | — |"
                )
        lines.append("")

    # ============================================================
    # Positions
    # ============================================================
    lines.append("## Positions")
    lines.append("")
    if ctx.portfolio.positions:
        lines.append("| Security | Shares | Avg Cost | Market Value |")
        lines.append("|----------|--------|----------|-------------|")
        for sec, pos in ctx.portfolio.positions.items():
            if pos.amount > 0:
                lines.append(f"| {sec} | {pos.amount:,} | {pos.avg_cost:.3f} | {pos.total_value:,.2f} |")
    else:
        lines.append("Flat (no positions).")
    lines.append("")

    # ============================================================
    # Factor Analysis
    # ============================================================
    ff = fama_french_analysis(result)
    if ff:
        lines.append("## Factor Analysis")
        lines.append("")
        lines.append("| Factor | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Market Beta | {ff['market_beta']:.2f} |")
        lines.append(f"| Market Exposure | {ff['market_exposure']:+.2f} |")
        lines.append(f"| Annual Alpha | {ff['alpha_annual']:+.2%} |")
        lines.append(f"| Momentum Correlation | {ff['momentum_correlation']:.3f} |")
        lines.append(f"| Residual Volatility | {ff['residual_volatility']:.2%} |")
        lines.append(f"| Explained Variance (R²) | {ff['explained_variance']:.2%} |")
        lines.append("")

    # ============================================================
    # Brinson Attribution
    # ============================================================
    br = brinson_attribution(result)
    if br:
        lines.append("## Brinson Attribution")
        lines.append("")
        lines.append("| Component | Effect |")
        lines.append("|-----------|--------|")
        lines.append(f"| Allocation | {br['allocation_effect']:+.2%} |")
        lines.append(f"| Selection | {br['selection_effect']:+.2%} |")
        lines.append(f"| Interaction | {br['interaction_effect']:+.2%} |")
        lines.append(f"| Total Active Return | {br['total_active_return']:+.2%} |")
        lines.append("")

    # ============================================================
    # Data Sources & Methodology
    # ============================================================
    lines.append("## Data Sources")
    lines.append("")
    lines.append("| Source | Details |")
    lines.append("|--------|---------|")
    lines.append("| Market Data | AKShare `stock_zh_a_hist` (EastMoney), forward-adjusted daily OHLCV |")
    lines.append("| Benchmark | CSI 300 (000300) / SSE Composite (000001) via AKShare `stock_zh_index_daily_em` |")
    lines.append("| Risk-Free Rate | 3.0% per annum (approximate Chinese government bond rate), daily = 3% ÷ 252 |")
    lines.append("| Backtest Engine | EasyQuant eqlib — event-driven, T+1, per-leg commission applied |")
    lines.append("")

    lines.append("## Metric Definitions")
    lines.append("")
    lines.append("| Metric | Formula / Method | Reference |")
    lines.append("|--------|-----------------|-----------|")
    lines.append("| Annual Return | `(1 + total_return)^(252/N) - 1` | Standard annualization |")
    lines.append("| Sharpe Ratio | `(E[R_p] - r_f) / σ_p × √252` | Sharpe (1966, 1994) |")
    lines.append("| Sortino Ratio | `(E[R_p] - r_f) / σ_down × √252` (downside vol only) | Sortino & Price (1994) |")
    lines.append("| Max Drawdown | `max[(peak - trough) / peak]` | Magdon-Ismail & Atiya (2004) |")
    lines.append("| Calmar Ratio | `annual_return / |max_drawdown|` | Young (1991) |")
    lines.append("| Alpha | `R_p(ann) - [r_f + β × (R_m(ann) - r_f)]` | Jensen (1968), CAPM |")
    lines.append("| Beta | `Cov(R_p, R_m) / Var(R_m)` vs CSI 300 | Sharpe (1964), Lintner (1965) |")
    lines.append("| Win Rate | Profitable pairs / total FIFO-matched pairs | Van Tharp (1999) |")
    lines.append("")
    lines.append("> **Disclaimer:** This report is generated by EasyQuant for research purposes only and")
    lines.append("> does not constitute investment advice. Past performance is not indicative of future results.")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report saved: {out_path}")


def generate_report_json(result, out_path):
    """Generate machine-readable JSON report with risk metrics,
    benchmark comparison, and full trade/position data.
    """
    from eqlib.attribution import analyze_returns, brinson_attribution, fama_french_analysis
    from eqlib.data import fetch_stock_data

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    analytics = analyze_returns(result)

    # Benchmark data
    bench_return = None
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_init = bench_df["close"].iloc[0]
            bench_final = bench_df["close"].iloc[-1]
            bench_return = (bench_final - bench_init) / bench_init
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
                "cumulative_return": round(r["total_value"] / initial - 1, 6),
            })

    report = {
        "metadata": {
            "generated_at": str(datetime.datetime.now().replace(microsecond=0)),
            "generator": "EasyQuant eqlib",
            "data_sources": {
                "market_data": "AKShare stock_zh_a_hist (EastMoney), forward-adjusted daily OHLCV",
                "benchmark_data": "AKShare stock_zh_index_daily_em (EastMoney)",
                "risk_free_rate": "3.0% per annum (approximate Chinese government bond rate)",
            },
            "methodology": {
                "annual_return": "(1 + total_return)^(252/N) - 1, N = trading days",
                "sharpe_ratio": "(E[R_p] - r_f) / sigma_p * sqrt(252); ref: Sharpe (1966)",
                "sortino_ratio": "(E[R_p] - r_f) / sigma_down * sqrt(252); ref: Sortino & Price (1994)",
                "max_drawdown": "max[(peak - trough) / peak]; ref: Magdon-Ismail & Atiya (2004)",
                "calmar_ratio": "annual_return / |max_drawdown|; ref: Young (1991)",
                "alpha_beta": "CAPM vs CSI300; ref: Sharpe (1964), Lintner (1965)",
                "win_rate": "profitable FIFO-matched pairs / total pairs",
            },
            "disclaimer": "For research purposes only. Not investment advice.",
        },
        "summary": {
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
        },
        "risk_metrics": None,
        "trades": [
            {
                "type": t["type"],
                "date": str(t["date"]),
                "security": t["security"],
                "price": t["price"],
                "amount": t["amount"],
                "commission": round(t.get("commission", 0), 2),
            }
            for t in trade_log
        ],
        "positions": {
            sec: {
                "amount": pos.amount,
                "avg_cost": round(pos.avg_cost, 3),
                "total_value": round(pos.total_value, 2),
            }
            for sec, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        },
        "cumulative_returns": cumulative_returns,
    }

    # Add risk metrics
    if analytics:
        report["risk_metrics"] = {
            "total_return": round(analytics["total_return"], 4),
            "annual_return": round(analytics["annual_return"], 4),
            "annual_volatility": round(analytics["annual_volatility"], 4),
            "sharpe_ratio": round(analytics["sharpe_ratio"], 2),
            "sortino_ratio": round(analytics["sortino_ratio"], 2),
            "max_drawdown": round(analytics["max_drawdown"], 4),
            "max_drawdown_start": str(analytics["max_drawdown_start"]) if analytics.get("max_drawdown_start") else None,
            "max_drawdown_end": str(analytics["max_drawdown_end"]) if analytics.get("max_drawdown_end") else None,
            "calmar_ratio": round(analytics["calmar_ratio"], 2),
            "alpha": round(analytics["alpha"], 4),
            "beta": round(analytics["beta"], 2),
            "information_ratio": round(analytics["information_ratio"], 2),
            "win_rate_daily": round(analytics["win_rate"], 4),
            "win_rate_trade": round(analytics["win_rate_trade"], 4),
            "win_count": analytics.get("win_count", 0),
            "loss_count": analytics.get("loss_count", 0),
            "profit_loss_ratio": round(analytics.get("profit_loss_ratio", 0), 2),
            "annual_turnover": round(analytics["annual_turnover"], 4),
            "total_commission": round(analytics["total_commission"], 2),
            "net_return": round(analytics["net_return"], 4),
            "trading_days": analytics["trading_days"],
            "benchmark_volatility": round(analytics.get("benchmark_volatility", 0), 4),
        }

        # Excess return metrics
        report["excess_return_metrics"] = {
            "excess_return": round(analytics.get("excess_return", 0), 4),
            "benchmark_return": round(analytics.get("benchmark_return", 0), 4),
            "excess_return_max_drawdown": round(analytics.get("excess_return_max_drawdown", 0), 4),
            "excess_return_sharpe": round(analytics.get("excess_return_sharpe", 0), 2),
            "daily_excess_return": round(analytics.get("daily_excess_return", 0), 6),
        }

    # Brinson attribution
    br = brinson_attribution(result)
    if br:
        report["brinson_attribution"] = {
            "allocation_effect": round(br["allocation_effect"], 4),
            "selection_effect": round(br["selection_effect"], 4),
            "interaction_effect": round(br["interaction_effect"], 4),
            "total_active_return": round(br["total_active_return"], 4),
        }

    # Factor analysis
    ff = fama_french_analysis(result)
    if ff:
        report["factor_analysis"] = {
            "market_beta": round(ff["market_beta"], 2),
            "market_exposure": round(ff["market_exposure"], 2),
            "alpha_annual": round(ff["alpha_annual"], 4),
            "momentum_correlation": round(ff["momentum_correlation"], 3),
            "residual_volatility": round(ff["residual_volatility"], 4),
            "explained_variance": round(ff["explained_variance"], 4),
        }

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Data saved: {out_path}")
