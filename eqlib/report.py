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
                "color": "#26a69a" if daily_pnl >= 0 else "#ef5350",
            })
            ret_bars.append({
                "time": d, "value": daily_ret,
                "color": "#26a69a" if daily_ret >= 0 else "#ef5350",
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
    # K-line + technical indicators
    # ============================================================
    candlestick_data = []
    ma5_data = []
    ma20_data = []
    ma60_data = []
    volume_data = []
    support_data = []
    resistance_data = []
    pivot_r1_data = []
    pivot_s1_data = []

    df = fetch_stock_data(symbol, start, end)
    if not df.empty:
        df_sorted = df.sort_index()
        closes = df_sorted["close"]
        highs = df_sorted["high"]
        lows = df_sorted["low"]
        ma5 = closes.rolling(5).mean()
        ma20 = closes.rolling(20).mean()
        ma60 = closes.rolling(60).mean()
        support, resistance = _compute_support_resistance(closes, highs, lows, window=20)
        r1, s1, _, _ = _compute_pivot_points(df_sorted, window=20)

        for (date, row), m5, m20, m60, sup, res, pr1, ps1 in zip(
                df_sorted.iterrows(), ma5, ma20, ma60, support, resistance, r1, s1):
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
            if not pd.isna(pr1):
                pivot_r1_data.append({"time": d, "value": round(float(pr1), 3)})
            if not pd.isna(ps1):
                pivot_s1_data.append({"time": d, "value": round(float(ps1), 3)})

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
    # Benchmark returns (沪深300 + 上证指数)
    # ============================================================
    csi300_data = _fetch_index_returns("sh000300", start, end, recorded)
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
    metrics = _calc_metrics(recorded, trade_log, initial, final, csi300_data)

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
            "high_52w": round(float(df_s["high"].max()), 3),
            "low_52w": round(float(df_s["low"].min()), 3),
        }

    # ============================================================
    # Build HTML
    # ============================================================
    bench_code = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    bench_label = {"000300": "沪深300", "000001": "上证指数"}.get(bench_code, bench_code)

    html = _HTML_TEMPLATE.format(
        symbol=symbol,
        start_date=str(start),
        end_date=str(end),
        initial_capital=f"{initial:,.2f}",
        final_value=f"{final:,.2f}",
        pnl=f"{pnl:+,.2f}",
        pnl_pct=f"{pnl_pct:+.2f}%",
        pnl_color=pnl_color,
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
        pivot_r1_json=json.dumps(pivot_r1_data),
        pivot_s1_json=json.dumps(pivot_s1_data),
        cum_return_json=json.dumps(cum_return_data),
        csi300_json=json.dumps(csi300_data),
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
    atr = tr.rolling(period, min_periods=1).mean()
    return atr.iloc[-1] if not atr.empty else None


def _calc_metrics(recorded, trade_log, initial, final, benchmark_data):
    """Calculate performance metrics."""
    metrics = {
        "sharpe": "N/A", "sortino": "N/A", "max_dd": "N/A", "max_dd_pct": "N/A",
        "ann_ret": "N/A", "ann_ret_pct": "N/A", "win_rate": "N/A",
        "benchmark_ret": "N/A", "benchmark_ret_pct": "N/A",
        "alpha": "N/A", "beta": "N/A",
    }

    if not recorded or len(recorded) < 2:
        return metrics

    entries = sorted(recorded.values(), key=lambda x: x.get("date", datetime.date.min)) if isinstance(recorded, dict) else recorded

    # Extract unique daily values
    by_date = {}
    for r in entries:
        if "total_value" in r:
            d = _to_tv_date(r["date"])
            by_date[d] = r["total_value"]

    values = [by_date[k] for k in sorted(by_date.keys()) if by_date[k] > 0]
    if len(values) < 2:
        return metrics

    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    ret_series = pd.Series(returns)

    n_days = len(returns)
    total_ret = final / initial - 1
    years = n_days / 252
    if years > 0:
        ann_ret = (1 + total_ret) ** (1 / years) - 1
        metrics["ann_ret"] = f"{ann_ret:.2%}"
        metrics["ann_ret_pct"] = f"{ann_ret:+.2f}%"

    rf_daily = 0.03 / 252
    if ret_series.std() > 0:
        sharpe = (ret_series.mean() - rf_daily) / ret_series.std() * (252 ** 0.5)
        metrics["sharpe"] = f"{sharpe:.2f}"

    downside = ret_series[ret_series < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = (ret_series.mean() - rf_daily) / downside.std() * (252 ** 0.5)
        metrics["sortino"] = f"{sortino:.2f}"

    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd
    metrics["max_dd"] = f"{max_dd:.2%}"
    metrics["max_dd_pct"] = f"{-max_dd:.2f}%"

    if trade_log:
        buys = [t for t in trade_log if t["type"] == "BUY"]
        sells = [t for t in trade_log if t["type"] == "SELL"]
        n_pairs = min(len(buys), len(sells))
        wins = sum(1 for i in range(n_pairs) if sells[i]["price"] > buys[i]["price"])
        if n_pairs > 0:
            metrics["win_rate"] = f"{wins / n_pairs:.0%}"

    if benchmark_data and len(benchmark_data) > 0:
        last_bm = benchmark_data[-1]["value"]
        bm_ret = last_bm / 100  # already in %
        metrics["benchmark_ret"] = f"{bm_ret:.2%}"
        metrics["benchmark_ret_pct"] = f"{bm_ret:+.2f}%"

        if len(benchmark_data) > 1:
            bm_values = [b["value"] for b in benchmark_data]
            bm_returns = []
            for i in range(1, len(bm_values)):
                if bm_values[i-1] == 0:
                    bm_returns.append(0)
                else:
                    bm_returns.append((bm_values[i] - bm_values[i-1]) / bm_values[i-1])
            if len(bm_returns) > 1:
                bm_series = pd.Series(bm_returns)
                cov = ret_series.cov(bm_series)
                bm_var = bm_series.var()
                if bm_var > 0:
                    beta_val = cov / bm_var
                    metrics["beta"] = f"{beta_val:.3f}"
                    alpha_ann = ann_ret - (0.03 + beta_val * (bm_ret / years - 0.03)) if years > 0 else 0
                    metrics["alpha"] = f"{alpha_ann:.2%}"

    return metrics


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测报告 · {symbol}</title>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0a0e17; color: #c8d6e5; line-height: 1.5;
  }}
  .header {{
    background: linear-gradient(180deg, #0f1923 0%, #0a0e17 100%);
    border-bottom: 1px solid #1e2d3d; padding: 28px 0 24px;
  }}
  .header-inner {{ max-width: 1600px; margin: 0 auto; padding: 0 32px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  h1 {{ font-size: 26px; font-weight: 700; color: #eaf2fb; letter-spacing: -0.3px; }}
  h1 .sym {{ color: #5b9cf6; }}
  .header-meta {{ font-size: 13px; color: #5a6f84; }}
  .container {{ max-width: 100%; padding: 0 32px 40px; }}

  /* Summary row */
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 20px 0; }}
  .card {{ background: #111b27; border: 1px solid #1e2d3d; border-radius: 10px; padding: 14px 16px; transition: border-color 0.2s; }}
  .card:hover {{ border-color: #2a3f55; }}
  .card .label {{ font-size: 11px; color: #5a6f84; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 500; }}
  .card .value {{ font-size: 18px; font-weight: 700; color: #eaf2fb; font-variant-numeric: tabular-nums; }}

  /* Chart panels */
  .chart-panel {{
    background: #111b27; border: 1px solid #1e2d3d; border-radius: 10px;
    padding: 16px 18px; margin-bottom: 14px;
  }}
  .chart-panel h2 {{ font-size: 13px; color: #5a6f84; margin-bottom: 10px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
  .chart-panel h2::before {{ content: ""; width: 3px; height: 14px; background: #5b9cf6; border-radius: 2px; }}
  #kline {{ width: 100%; height: 480px; }}
  #returns {{ width: 100%; height: 240px; }}
  #drawdown {{ width: 100%; height: 160px; }}
  #pnlbar {{ width: 100%; height: 160px; }}
  #dailyret {{ width: 100%; height: 160px; }}

  /* Metrics */
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 10px; margin: 18px 0; }}
  .metric-card {{ background: #111b27; border: 1px solid #1e2d3d; border-radius: 10px; padding: 14px 16px; }}
  .metric-card .title {{ font-size: 10px; color: #5a6f84; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }}
  .metric-card .val {{ font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; }}

  /* Technical stats */
  .tech-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 10px; margin: 18px 0; }}
  .tech-card {{ background: #111b27; border: 1px solid #1e2d3d; border-radius: 10px; padding: 14px 16px; }}
  .tech-card .title {{ font-size: 10px; color: #5a6f84; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }}
  .tech-card .val {{ font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }}

  /* Legend */
  .legend {{ display: flex; gap: 16px; margin-bottom: 10px; font-size: 12px; flex-wrap: wrap; align-items: center; }}
  .legend span {{ display: flex; align-items: center; gap: 5px; color: #8a9bb0; }}
  .legend .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
  .legend .dash {{ width: 16px; height: 0; border-top: 2px dashed; display: inline-block; }}

  /* Tables */
  .trade-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .trade-table th {{ text-align: left; padding: 10px 8px; border-bottom: 2px solid #1e2d3d; color: #5a6f84; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .trade-table td {{ padding: 8px; border-bottom: 1px solid #16202c; font-variant-numeric: tabular-nums; }}
  .trade-table tr:hover {{ background: #16202c; }}
  .calendar-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .calendar-table th {{ text-align: left; padding: 8px; border-bottom: 2px solid #1e2d3d; color: #5a6f84; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; background: #111b27; z-index: 1; }}
  .calendar-table td {{ padding: 6px 8px; border-bottom: 1px solid #16202c; vertical-align: top; }}
  .calendar-wrapper {{ max-height: 480px; overflow-y: auto; }}

  /* Sections & tabs */
  .section {{ background: #111b27; border: 1px solid #1e2d3d; border-radius: 10px; padding: 20px; margin-bottom: 14px; }}
  .section h2 {{ font-size: 15px; color: #eaf2fb; margin-bottom: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
  .section h2::before {{ content: ""; width: 3px; height: 16px; background: #5b9cf6; border-radius: 2px; }}
  ul {{ list-style: none; padding: 0; }}
  ul li {{ padding: 6px 0; color: #c8d6e5; border-bottom: 1px solid #16202c; }}
  ul li:last-child {{ border-bottom: none; }}
  .tab-bar {{ display: flex; gap: 0; margin-bottom: 14px; border-bottom: 1px solid #1e2d3d; }}
  .tab {{ padding: 10px 18px; cursor: pointer; font-size: 13px; color: #5a6f84; border-bottom: 2px solid transparent; transition: all 0.2s; }}
  .tab:hover {{ color: #c8d6e5; }}
  .tab.active {{ color: #5b9cf6; border-bottom-color: #5b9cf6; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}

  .footer {{ text-align: center; padding: 24px 0; color: #2a3f55; font-size: 12px; }}
  .pos {{ color: #00c087; }}
  .neg {{ color: #f04848; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <h1>回测报告 · <span class="sym">{symbol}</span></h1>
    <div class="header-meta">{start_date} &rarr; {end_date}</div>
  </div>
</div>

<div class="container">

  <!-- Summary cards -->
  <div class="summary">
    <div class="card"><div class="label">初始资金</div><div class="value">{initial_capital}</div></div>
    <div class="card"><div class="label">期末净值</div><div class="value">{final_value}</div></div>
    <div class="card"><div class="label">盈亏</div><div class="value" style="color:{pnl_color}">{pnl} ({pnl_pct})</div></div>
    <div class="card"><div class="label">买入次数</div><div class="value">{buy_count}</div></div>
    <div class="card"><div class="label">卖出次数</div><div class="value">{sell_count}</div></div>
  </div>

  <!-- Performance metrics -->
  <div class="metrics-grid">
    <div class="metric-card"><div class="title">年化收益</div><div class="val">{ann_ret}</div></div>
    <div class="metric-card"><div class="title">Sharpe 比率</div><div class="val">{sharpe}</div></div>
    <div class="metric-card"><div class="title">Sortino 比率</div><div class="val">{sortino}</div></div>
    <div class="metric-card"><div class="title">最大回撤</div><div class="val neg">{max_dd}</div></div>
    <div class="metric-card"><div class="title">胜率</div><div class="val">{win_rate}</div></div>
    <div class="metric-card"><div class="title">Alpha</div><div class="val">{alpha}</div></div>
    <div class="metric-card"><div class="title">Beta</div><div class="val">{beta}</div></div>
    <div class="metric-card"><div class="title">沪深300 收益</div><div class="val">{benchmark_ret}</div></div>
  </div>

  <!-- Technical stats -->
  <div class="tech-grid" id="tech-stats"></div>

  <!-- K-line chart -->
  <div class="chart-panel">
    <h2>K 线图 · 成交量</h2>
    <div class="legend">
      <span><span class="dot" style="background:#2196F3"></span> MA5</span>
      <span><span class="dot" style="background:#FF9800"></span> MA20</span>
      <span><span class="dot" style="background:#AB47BC"></span> MA60</span>
      <span><span class="dash" style="border-color:rgba(42,179,142,0.6)"></span> 支撑位</span>
      <span><span class="dash" style="border-color:rgba(240,72,72,0.6)"></span> 压力位</span>
      <span><span class="dot" style="background:#00c087"></span> 买入</span>
      <span><span class="dot" style="background:#f04848"></span> 卖出</span>
    </div>
    <div id="kline"></div>
  </div>

  <!-- Cumulative Returns: Strategy vs 沪深300 vs 上证指数 -->
  <div class="chart-panel">
    <h2>累计收益率对比</h2>
    <div class="legend">
      <span><span class="dot" style="background:#00c087"></span> 策略</span>
      <span><span class="dot" style="background:#5b9cf6"></span> 沪深300</span>
      <span><span class="dot" style="background:#f5a623"></span> 上证指数</span>
    </div>
    <div id="returns"></div>
  </div>

  <!-- Drawdown -->
  <div class="chart-panel">
    <h2>回撤曲线</h2>
    <div id="drawdown"></div>
  </div>

  <!-- Daily P&L -->
  <div class="chart-panel">
    <h2>每日盈亏（绝对额）</h2>
    <div class="legend">
      <span><span class="dot" style="background:#00c087"></span> 盈利</span>
      <span><span class="dot" style="background:#f04848"></span> 亏损</span>
    </div>
    <div id="pnlbar"></div>
  </div>

  <!-- Daily Returns -->
  <div class="chart-panel">
    <h2>每日收益率（%）</h2>
    <div id="dailyret"></div>
  </div>

  <!-- Trade detail & Calendar -->
  <div class="section">
    <h2>交易明细与日历</h2>
    <div class="tab-bar">
      <div class="tab active" data-tab="trade-table">交易明细</div>
      <div class="tab" data-tab="trade-calendar">交易日历</div>
      <div class="tab" data-tab="positions">当前持仓</div>
    </div>

    <div id="trade-table" class="tab-content active">
      <table class="trade-table">
        <thead><tr><th>#</th><th>日期</th><th>操作</th><th>代码</th><th>价格</th><th>数量</th><th>手续费</th></tr></thead>
        <tbody>{trade_rows}</tbody>
      </table>
    </div>

    <div id="trade-calendar" class="tab-content">
      <div class="calendar-wrapper">
        <table class="calendar-table">
          <thead><tr><th>日期</th><th>累计收益</th><th>回撤</th><th>操作</th></tr></thead>
          <tbody>{calendar_rows}</tbody>
        </table>
      </div>
    </div>

    <div id="positions" class="tab-content">
      <ul>{positions_html}</ul>
    </div>
  </div>

</div>

<div class="footer">
  EasyQuant · Generated with eqlib
</div>

<script>
(function() {{
  const commonOpts = {{
    layout: {{ background: {{ type: 'solid', color: '#111b27' }}, textColor: '#5a6f84', fontSize: 11, fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif' }},
    grid: {{ vertLines: {{ color: '#16202c' }}, horzLines: {{ color: '#16202c' }} }},
    timeScale: {{ borderColor: '#1e2d3d', timeVisible: false, borderColor: '#1e2d3d' }},
    rightPriceScale: {{ borderColor: '#1e2d3d' }},
    crosshair: {{ mode: 1, vertLine: {{ color: '#2a3f55', width: 1, style: 2, labelBackgroundColor: '#2a3f55' }}, horzLine: {{ color: '#2a3f55', width: 1, style: 2, labelBackgroundColor: '#2a3f55' }} }},
  }};

  // ====== K-line Chart ======
  const klineEl = document.getElementById('kline');
  const klineChart = LightweightCharts.createChart(klineEl, {{
    ...commonOpts, width: klineEl.clientWidth, height: 480,
    rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.22 }} }},
  }});

  const candleSeries = klineChart.addCandlestickSeries({{
    upColor: '#00c087', downColor: '#f04848',
    borderUpColor: '#00c087', borderDownColor: '#f04848',
    wickUpColor: '#00c087', wickDownColor: '#f04848',
  }});
  candleSeries.setData({candlestick_json});
  candleSeries.setMarkers({markers_json});

  // MA lines
  const ma5s = klineChart.addLineSeries({{ color: '#2196F3', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }});
  ma5s.setData({ma5_json});
  const ma20s = klineChart.addLineSeries({{ color: '#FF9800', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }});
  ma20s.setData({ma20_json});
  const ma60s = klineChart.addLineSeries({{ color: '#AB47BC', lineWidth: 1, lineStyle: 0, priceLineVisible: false, lastValueVisible: false }});
  ma60s.setData({ma60_json});

  // Support / Resistance (dashed)
  const supSeries = klineChart.addLineSeries({{
    color: 'rgba(42,179,142,0.55)', lineWidth: 1, lineStyle: 2,
    priceLineVisible: false, lastValueVisible: false,
  }});
  supSeries.setData({support_json});

  const resSeries = klineChart.addLineSeries({{
    color: 'rgba(240,72,72,0.55)', lineWidth: 1, lineStyle: 2,
    priceLineVisible: false, lastValueVisible: false,
  }});
  resSeries.setData({resistance_json});

  // Volume
  const volSeries = klineChart.addHistogramSeries({{
    priceFormat: {{ type: 'volume' }},
    priceScaleId: 'vol',
  }});
  volSeries.priceScale().applyOptions({{ scaleMargins: {{ top: 0.8, bottom: 0 }} }});
  volSeries.setData({volume_json});

  klineChart.timeScale().fitContent();

  // ====== Cumulative Returns ======
  const retEl = document.getElementById('returns');
  const retChart = LightweightCharts.createChart(retEl, {{
    ...commonOpts, width: retEl.clientWidth, height: 240,
  }});

  const stratS = retChart.addAreaSeries({{
    lineColor: '#00c087', topColor: 'rgba(0,192,135,0.25)', bottomColor: 'rgba(0,192,135,0)',
    lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
  }});
  stratS.setData({cum_return_json});

  const csi300S = retChart.addLineSeries({{
    color: '#5b9cf6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
  }});
  csi300S.setData({csi300_json});

  const sseS = retChart.addLineSeries({{
    color: '#f5a623', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
  }});
  sseS.setData({sse_json});

  retChart.timeScale().fitContent();

  // ====== Drawdown ======
  const ddEl = document.getElementById('drawdown');
  const ddChart = LightweightCharts.createChart(ddEl, {{
    ...commonOpts, width: ddEl.clientWidth, height: 160,
    rightPriceScale: {{ scaleMargins: {{ top: 0.1, bottom: 0.05 }} }},
  }});
  const ddS = ddChart.addAreaSeries({{
    lineColor: '#f04848', topColor: 'rgba(240,72,72,0.20)', bottomColor: 'rgba(240,72,72,0)',
    lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
  }});
  ddS.setData({drawdown_json});
  ddChart.timeScale().fitContent();

  // ====== Daily P&L ======
  const pnlEl = document.getElementById('pnlbar');
  const pnlChart = LightweightCharts.createChart(pnlEl, {{
    ...commonOpts, width: pnlEl.clientWidth, height: 160,
  }});
  const pnlS = pnlChart.addHistogramSeries({{ priceFormat: {{ type: 'volume' }} }});
  pnlS.setData({pnl_bar_json});
  pnlChart.timeScale().fitContent();

  // ====== Daily Returns ======
  const drEl = document.getElementById('dailyret');
  const drChart = LightweightCharts.createChart(drEl, {{
    ...commonOpts, width: drEl.clientWidth, height: 160,
  }});
  const drS = drChart.addHistogramSeries({{ priceFormat: {{ type: 'percent' }} }});
  drS.setData({daily_returns_json});
  drChart.timeScale().fitContent();

  // ====== Sync all time scales ======
  const allCharts = [klineChart, retChart, ddChart, pnlChart, drChart];
  allCharts.forEach(chart => {{
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
      if (!range) return;
      allCharts.forEach(c => {{ if (c !== chart) c.timeScale().setVisibleLogicalRange(range); }});
    }});
  }});

  // ====== Responsive ======
  let resizeTimer;
  window.addEventListener('resize', () => {{
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {{
      klineChart.applyOptions({{ width: klineEl.clientWidth }});
      retChart.applyOptions({{ width: retEl.clientWidth }});
      ddChart.applyOptions({{ width: ddEl.clientWidth }});
      pnlChart.applyOptions({{ width: pnlEl.clientWidth }});
      drChart.applyOptions({{ width: drEl.clientWidth }});
    }}, 150);
  }});

  // ====== Technical stats cards ======
  const tech = {tech_json};
  const techEl = document.getElementById('tech-stats');
  if (Object.keys(tech).length > 0) {{
    const items = [
      ['最新价', tech.latest_price],
      ['MA5', tech.ma5],
      ['MA20', tech.ma20],
      ['MA60', tech.ma60],
      ['ATR(14)', tech.atr14],
      ['量比', tech.vol_ratio],
      ['52周高', tech.high_52w],
      ['52周低', tech.low_52w],
    ].filter(([,v]) => v !== null && v !== undefined);
    techEl.className = 'tech-grid';
    techEl.innerHTML = items.map(([label, val]) =>
      `<div class="tech-card"><div class="title">${{label}}</div><div class="val">${{typeof val === 'number' ? val.toLocaleString() : val}}</div></div>`
    ).join('');
  }}

  // ====== Tabs ======
  document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
      const parent = tab.closest('.section');
      parent.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.tab).classList.add('active');
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
                lines.append(
                    f"| {len(lines)} | {sec} | {buy_t['date']} | {buy_t['price']:.3f} "
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
            "win_rate": round(analytics["win_rate"], 4),
            "trading_days": analytics["trading_days"],
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
