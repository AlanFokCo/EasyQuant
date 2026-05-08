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
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
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

    downside_returns = ret_series - rf_daily
    downside_sq = downside_returns[downside_returns < 0] ** 2
    downside_dev = (downside_sq.mean() ** 0.5) * (252 ** 0.5) if len(downside_sq) > 0 else 0
    if downside_dev > 0:
        sortino = (ret_series.mean() * 252 - 0.03) / downside_dev
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
        from eqlib.attribution import _calc_trade_win_rate
        win_rate_val, n_pairs = _calc_trade_win_rate(trade_log)
        if n_pairs > 0:
            metrics["win_rate"] = f"{win_rate_val:.0%}"

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
                    bm_ann_ret = (1 + bm_ret) ** (1 / years) - 1
                    alpha_ann = ann_ret - (0.03 + beta_val * (bm_ann_ret - 0.03)) if years > 0 else 0
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
  :root {{
    --bg: #0a0e17; --surface: #111b27; --surface2: #16202c;
    --border: #1e2d3d; --border2: #2a3f55;
    --text: #c8d6e5; --text-dim: #5a6f84; --text-bright: #eaf2fb;
    --blue: #5b9cf6; --green: #00c087; --red: #f04848; --yellow: #f5a623;
    --radius: 10px; --radius-sm: 6px;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC",
      "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.55; font-size: 14px;
  }}
  /* Header */
  .header {{
    background: linear-gradient(160deg, #0f1f30 0%, var(--bg) 100%);
    border-bottom: 1px solid var(--border); padding: 22px 0 18px;
  }}
  .header-inner {{
    max-width: 1600px; margin: 0 auto; padding: 0 32px;
    display: flex; align-items: flex-start; justify-content: space-between;
    flex-wrap: wrap; gap: 12px;
  }}
  h1 {{ font-size: 21px; font-weight: 700; color: var(--text-bright); letter-spacing: -.3px; }}
  h1 .sym {{ color: var(--blue); }}
  .header-meta {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; line-height: 1.6; }}
  .pnl-badge {{
    display: inline-flex; align-items: center; padding: 6px 14px;
    border-radius: 20px; font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums;
  }}
  .pnl-badge.pos {{ background: rgba(0,192,135,.14); color: var(--green); border: 1px solid rgba(0,192,135,.3); }}
  .pnl-badge.neg {{ background: rgba(240,72,72,.14); color: var(--red); border: 1px solid rgba(240,72,72,.3); }}
  /* Container */
  .container {{ max-width: 1600px; margin: 0 auto; padding: 0 32px 48px; }}
  /* Summary cards */
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 10px; margin: 18px 0 12px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; transition: border-color .2s; }}
  .card:hover {{ border-color: var(--border2); }}
  .card .label {{ font-size: 10px; color: var(--text-dim); margin-bottom: 5px; text-transform: uppercase; letter-spacing: .7px; font-weight: 500; }}
  .card .value {{ font-size: 19px; font-weight: 700; color: var(--text-bright); font-variant-numeric: tabular-nums; }}
  /* Section title */
  .section-title {{
    font-size: 11px; color: var(--text-dim); font-weight: 600;
    text-transform: uppercase; letter-spacing: .7px;
    display: flex; align-items: center; gap: 8px; margin: 18px 0 10px;
  }}
  .section-title::before {{ content: ""; width: 3px; height: 12px; background: var(--blue); border-radius: 2px; }}
  /* Metric cards */
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(162px, 1fr)); gap: 10px; margin-bottom: 14px; }}
  .metric-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 14px 16px; cursor: pointer; transition: border-color .2s, box-shadow .2s; user-select: none;
  }}
  .metric-card:hover {{ border-color: var(--blue); box-shadow: 0 0 0 1px rgba(91,156,246,.18); }}
  .metric-card .title-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }}
  .metric-card .mc-title {{ font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .6px; font-weight: 600; }}
  .mc-info {{
    width: 15px; height: 15px; border-radius: 50%; border: 1px solid var(--text-dim);
    display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700;
    color: var(--text-dim); opacity: .55; transition: opacity .2s, color .2s, border-color .2s; flex-shrink: 0;
  }}
  .metric-card:hover .mc-info {{ opacity: 1; color: var(--blue); border-color: var(--blue); }}
  .metric-card .mc-val {{ font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-bright); }}
  .mc-grade-row {{ margin-top: 6px; }}
  .mc-grade {{
    display: inline-flex; align-items: center; font-size: 9px; font-weight: 700;
    padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: .4px;
  }}
  .grade-excellent {{ background: rgba(0,192,135,.14); color: #00c087; border: 1px solid rgba(0,192,135,.28); }}
  .grade-good      {{ background: rgba(91,156,246,.14); color: #5b9cf6; border: 1px solid rgba(91,156,246,.28); }}
  .grade-fair      {{ background: rgba(245,166,35,.14); color: #f5a623; border: 1px solid rgba(245,166,35,.28); }}
  .grade-poor      {{ background: rgba(240,72,72,.14);  color: #f04848; border: 1px solid rgba(240,72,72,.28); }}
  /* Tech stats */
  .tech-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-bottom: 14px; }}
  .tech-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 11px 14px; transition: border-color .2s; }}
  .tech-card:hover {{ border-color: var(--border2); }}
  .tech-card .title {{ font-size: 10px; color: var(--text-dim); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .6px; font-weight: 600; }}
  .tech-card .val {{ font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; color: var(--text-bright); }}
  /* Chart panels */
  .chart-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; margin-bottom: 12px; }}
  .chart-panel-head {{ display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }}
  .chart-panel h2 {{
    font-size: 12px; color: var(--text-dim); font-weight: 600;
    display: flex; align-items: center; gap: 7px; text-transform: uppercase; letter-spacing: .6px;
  }}
  .chart-panel h2::before {{ content: ""; width: 3px; height: 12px; background: var(--blue); border-radius: 2px; flex-shrink: 0; }}
  .chart-desc {{ font-size: 11px; color: var(--text-dim); opacity: .75; max-width: 700px; line-height: 1.5; }}
  .chart-source {{ font-size: 10px; color: var(--text-dim); opacity: .5; margin-top: 6px; line-height: 1.6; }}
  .chart-source code {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 9px; }}
  #kline    {{ width: 100%; height: 500px; }}
  #returns  {{ width: 100%; height: 260px; }}
  #drawdown {{ width: 100%; height: 155px; }}
  #pnlbar   {{ width: 100%; height: 155px; }}
  #dailyret {{ width: 100%; height: 155px; }}
  /* Legend */
  .legend {{ display: flex; gap: 14px; font-size: 11px; flex-wrap: wrap; align-items: center; }}
  .legend span {{ display: flex; align-items: center; gap: 5px; color: #8a9bb0; }}
  .legend .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
  .legend .dash {{ width: 14px; height: 0; border-top: 2px dashed; display: inline-block; flex-shrink: 0; }}
  .legend .ln {{ width: 14px; height: 2px; display: inline-block; flex-shrink: 0; }}
  /* Modal */
  .modal-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,.72);
    z-index: 2000; display: flex; align-items: center; justify-content: center;
    opacity: 0; pointer-events: none; transition: opacity .2s; backdrop-filter: blur(4px);
  }}
  .modal-overlay.open {{ opacity: 1; pointer-events: all; }}
  .modal {{
    background: var(--surface); border: 1px solid var(--border2); border-radius: 14px;
    padding: 26px 28px; max-width: 480px; width: 92%; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 24px 64px rgba(0,0,0,.55);
    transform: translateY(-8px) scale(.98); transition: transform .2s; position: relative;
  }}
  .modal-overlay.open .modal {{ transform: translateY(0) scale(1); }}
  .modal-close {{
    position: absolute; top: 14px; right: 16px; background: none; border: none;
    color: var(--text-dim); font-size: 18px; cursor: pointer; line-height: 1; padding: 4px; transition: color .2s;
  }}
  .modal-close:hover {{ color: var(--text-bright); }}
  .modal h3 {{ font-size: 15px; font-weight: 700; color: var(--text-bright); margin-bottom: 4px; padding-right: 24px; }}
  .modal-cur {{ font-size: 30px; font-weight: 700; color: var(--blue); font-variant-numeric: tabular-nums; margin-bottom: 16px; }}
  .modal-sec {{ margin-bottom: 14px; }}
  .modal-sec h4 {{ font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .7px; font-weight: 600; margin-bottom: 5px; }}
  .modal-sec p {{ font-size: 12px; color: var(--text); line-height: 1.75; }}
  .modal-formula {{
    font-family: "SF Mono", "Fira Code", monospace; font-size: 12px;
    background: var(--surface2); padding: 8px 12px; border-radius: 6px;
    color: #a8d0f0; border: 1px solid var(--border); margin-top: 4px;
  }}
  .modal-ref {{ font-size: 10px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 10px; margin-top: 6px; line-height: 1.65; }}
  /* Sections / tables */
  .section {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; margin-bottom: 12px; }}
  .section > .section-title {{ margin-top: 0; }}
  .tab-bar {{ display: flex; border-bottom: 1px solid var(--border); margin-bottom: 14px; }}
  .tab {{ padding: 8px 16px; cursor: pointer; font-size: 12px; color: var(--text-dim); border-bottom: 2px solid transparent; transition: color .2s, border-color .2s; }}
  .tab:hover {{ color: var(--text); }}
  .tab.active {{ color: var(--blue); border-bottom-color: var(--blue); }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .trade-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .trade-table th {{ text-align: left; padding: 9px 10px; border-bottom: 2px solid var(--border); color: var(--text-dim); font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: .5px; }}
  .trade-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--surface2); font-variant-numeric: tabular-nums; }}
  .trade-table tr:hover td {{ background: var(--surface2); }}
  .cal-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .cal-table th {{ text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--border); color: var(--text-dim); font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: .5px; position: sticky; top: 0; background: var(--surface); z-index: 1; }}
  .cal-table td {{ padding: 6px 10px; border-bottom: 1px solid var(--surface2); vertical-align: top; font-size: 12px; }}
  .cal-wrapper {{ max-height: 400px; overflow-y: auto; }}
  /* Sources / methodology */
  .sources-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; }}
  .src-card {{ background: var(--surface2); border-radius: var(--radius-sm); padding: 12px 14px; }}
  .src-type {{ font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .5px; font-weight: 600; margin-bottom: 3px; }}
  .src-name {{ font-size: 13px; color: var(--text-bright); font-weight: 500; margin-bottom: 4px; }}
  .src-desc {{ font-size: 11px; color: var(--text-dim); line-height: 1.55; }}
  .src-desc code {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 10px; }}
  .method-list {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; }}
  .method-list li {{ background: var(--surface2); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 12px; color: var(--text); border-bottom: none !important; }}
  .method-list li strong {{ color: var(--text-bright); display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 3px; }}
  ul {{ list-style: none; padding: 0; }}
  ul li {{ padding: 7px 0; color: var(--text); border-bottom: 1px solid var(--surface2); font-size: 13px; }}
  ul li:last-child {{ border-bottom: none; }}
  /* Footer */
  .footer {{ text-align: center; padding: 20px 0 16px; color: var(--text-dim); font-size: 11px; border-top: 1px solid var(--border); margin-top: 4px; line-height: 1.8; }}
  .footer a {{ color: var(--blue); text-decoration: none; }}
  .footer a:hover {{ text-decoration: underline; }}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}
  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: var(--surface2); }}
  ::-webkit-scrollbar-thumb {{ background: var(--border2); border-radius: 3px; }}
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
    <div class="metric-card" onclick="showMetric('sharpe')">
      <div class="title-row"><span class="mc-title">Sharpe 比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-sharpe">{sharpe}</div>
      <div class="mc-grade-row"><div id="grade-sharpe"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('sortino')">
      <div class="title-row"><span class="mc-title">Sortino 比率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-sortino">{sortino}</div>
      <div class="mc-grade-row"><div id="grade-sortino"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('max_dd')">
      <div class="title-row"><span class="mc-title">最大回撤</span><span class="mc-info">i</span></div>
      <div class="mc-val neg" id="mv-max_dd">{max_dd}</div>
      <div class="mc-grade-row"><div id="grade-max_dd"></div></div>
    </div>
    <div class="metric-card" onclick="showMetric('win_rate')">
      <div class="title-row"><span class="mc-title">胜率</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-win_rate">{win_rate}</div>
      <div class="mc-grade-row"><div id="grade-win_rate"></div></div>
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
    <div class="metric-card" onclick="showMetric('bm_ret')">
      <div class="title-row"><span class="mc-title">{benchmark_name} 收益</span><span class="mc-info">i</span></div>
      <div class="mc-val" id="mv-bm_ret">{benchmark_ret}</div>
      <div class="mc-grade-row"><div id="grade-bm_ret"></div></div>
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
        <div class="chart-desc">日 K 线含 MA5/MA20/MA60 均线、20日动态支撑/压力位、成交量柱，以及买卖信号标记（&#9650; 买入 / &#9660; 卖出）。</div>
      </div>
      <div class="legend">
        <span><span class="dot" style="background:#2196F3"></span>MA5</span>
        <span><span class="dot" style="background:#FF9800"></span>MA20</span>
        <span><span class="dot" style="background:#AB47BC"></span>MA60</span>
        <span><span class="dash" style="border-color:rgba(42,179,142,0.65)"></span>支撑</span>
        <span><span class="dash" style="border-color:rgba(240,72,72,0.65)"></span>压力</span>
        <span><span class="dot" style="background:#00c087"></span>买入</span>
        <span><span class="dot" style="background:#f04848"></span>卖出</span>
      </div>
    </div>
    <div id="kline"></div>
    <div class="chart-source">
      数据来源：AKShare &middot; <code>stock_zh_a_hist</code>（东方财富），前复权日线 OHLCV。
      支撑/压力位：20日滚动最低/最高价（动态非静态）。
    </div>
  </div>

  <!-- Cumulative returns comparison -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <div>
        <h2>累计收益率对比</h2>
        <div class="chart-desc">策略与沪深300、上证综指在相同区间的累计收益率（%）横向对比，直观评估策略 Alpha 来源。各系列均以起始日收盘价归一化为 0%。</div>
      </div>
      <div class="legend">
        <span><span class="ln" style="background:#00c087"></span>策略</span>
        <span><span class="ln" style="background:#5b9cf6"></span>沪深300</span>
        <span><span class="ln" style="background:#f5a623"></span>上证指数</span>
      </div>
    </div>
    <div id="returns"></div>
    <div class="chart-source">
      基准数据：AKShare &middot; <code>stock_zh_index_daily_em</code>（东方财富）。
      沪深300（sh000300）&middot; 上证综指（sh000001）。
    </div>
  </div>

  <!-- Drawdown -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <div>
        <h2>回撤曲线</h2>
        <div class="chart-desc">策略净值相较历史峰值的累计回撤（%）。红色区域越深代表风险越大，是评估策略下行风险的核心指标。最大回撤 = max[(峰值 &minus; 谷值) / 峰值]。</div>
      </div>
    </div>
    <div id="drawdown"></div>
  </div>

  <!-- Daily P&L -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <div>
        <h2>每日盈亏（绝对额）</h2>
        <div class="chart-desc">每个交易日的资产净值变动额（元）。绿色为盈利日，红色为亏损日，可直观观察收益分布形态与连续亏损风险。</div>
      </div>
      <div class="legend">
        <span><span class="dot" style="background:#00c087"></span>盈利日</span>
        <span><span class="dot" style="background:#f04848"></span>亏损日</span>
      </div>
    </div>
    <div id="pnlbar"></div>
  </div>

  <!-- Daily returns -->
  <div class="chart-panel">
    <div class="chart-panel-head">
      <div>
        <h2>每日收益率（%）</h2>
        <div class="chart-desc">日度收益率分布，用于观察策略波动性（标准差）及收益连续性。高度偏度或厚尾特征可揭示潜在的尾部风险。</div>
      </div>
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
          <div class="src-desc">A股日线 OHLCV 行情通过 <code>stock_zh_a_hist</code> 获取，前复权处理。数据由东方财富网提供，仅供研究使用。</div>
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
      ref: 'Sharpe, W.F. (1966). Mutual Fund Performance. Journal of Business, 39(1), 119–138.\nSharpe, W.F. (1994). The Sharpe Ratio. Journal of Portfolio Management.',
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
      ref: 'Jensen, M.C. (1968). The Performance of Mutual Funds in the Period 1945-1964. Journal of Finance, 23(2), 389–416.\nCAPM: Sharpe (1964), Lintner (1965), Mossin (1966).',
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
      background: {{ type: 'solid', color: '#111b27' }},
      textColor: '#5a6f84', fontSize: 11,
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
    }},
    grid: {{ vertLines: {{ color: '#16202c' }}, horzLines: {{ color: '#16202c' }} }},
    timeScale: {{ borderColor: '#1e2d3d', timeVisible: false }},
    rightPriceScale: {{ borderColor: '#1e2d3d' }},
    crosshair: {{
      mode: 1,
      vertLine: {{ color: '#2a3f55', width: 1, style: 2, labelBackgroundColor: '#2a3f55' }},
      horzLine: {{ color: '#2a3f55', width: 1, style: 2, labelBackgroundColor: '#2a3f55' }},
    }},
  }};

  /* K-line */
  const kEl = document.getElementById('kline');
  const kChart = LightweightCharts.createChart(kEl, {{
    ...cmn, width: kEl.clientWidth, height: 500,
    rightPriceScale: {{ scaleMargins: {{ top: 0.05, bottom: 0.22 }} }},
  }});
  const cSeries = kChart.addCandlestickSeries({{
    upColor: '#00c087', downColor: '#f04848',
    borderUpColor: '#00c087', borderDownColor: '#f04848',
    wickUpColor: '#00c087', wickDownColor: '#f04848',
  }});
  cSeries.setData({candlestick_json});
  cSeries.setMarkers({markers_json});
  kChart.addLineSeries({{ color: '#2196F3', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma5_json});
  kChart.addLineSeries({{ color: '#FF9800', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma20_json});
  kChart.addLineSeries({{ color: '#AB47BC', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }}).setData({ma60_json});
  kChart.addLineSeries({{ color: 'rgba(42,179,142,0.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData({support_json});
  kChart.addLineSeries({{ color: 'rgba(240,72,72,0.55)',  lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }}).setData({resistance_json});
  const volS = kChart.addHistogramSeries({{ priceFormat: {{ type: 'volume' }}, priceScaleId: 'vol' }});
  volS.priceScale().applyOptions({{ scaleMargins: {{ top: 0.8, bottom: 0 }} }});
  volS.setData({volume_json});
  kChart.timeScale().fitContent();

  /* Cumulative returns */
  const rEl = document.getElementById('returns');
  const rChart = LightweightCharts.createChart(rEl, {{ ...cmn, width: rEl.clientWidth, height: 260 }});
  rChart.addAreaSeries({{
    lineColor: '#00c087', topColor: 'rgba(0,192,135,0.18)', bottomColor: 'rgba(0,192,135,0)',
    lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
  }}).setData({cum_return_json});
  rChart.addLineSeries({{ color: '#5b9cf6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true }}).setData({csi300_json});
  rChart.addLineSeries({{ color: '#f5a623', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true }}).setData({sse_json});
  rChart.timeScale().fitContent();

  /* Drawdown */
  const ddEl = document.getElementById('drawdown');
  const ddChart = LightweightCharts.createChart(ddEl, {{
    ...cmn, width: ddEl.clientWidth, height: 155,
    rightPriceScale: {{ scaleMargins: {{ top: 0.1, bottom: 0.05 }} }},
  }});
  ddChart.addAreaSeries({{
    lineColor: '#f04848', topColor: 'rgba(240,72,72,0.22)', bottomColor: 'rgba(240,72,72,0)',
    lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
  }}).setData({drawdown_json});
  ddChart.timeScale().fitContent();

  /* Daily P&L */
  const pEl = document.getElementById('pnlbar');
  const pChart = LightweightCharts.createChart(pEl, {{ ...cmn, width: pEl.clientWidth, height: 155 }});
  pChart.addHistogramSeries({{ priceFormat: {{ type: 'volume' }} }}).setData({pnl_bar_json});
  pChart.timeScale().fitContent();

  /* Daily returns */
  const drEl = document.getElementById('dailyret');
  const drChart = LightweightCharts.createChart(drEl, {{ ...cmn, width: drEl.clientWidth, height: 155 }});
  drChart.addHistogramSeries({{ priceFormat: {{ type: 'percent' }} }}).setData({daily_returns_json});
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

  /* Tabs */
  document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
      const sec = tab.closest('.section');
      sec.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      sec.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
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
