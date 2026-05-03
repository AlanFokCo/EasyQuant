"""Report generation: chart (PNG), JSON, and Markdown."""

import os
import json
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

plt.rcParams["font.sans-serif"] = ["PingFang HK", "Heiti TC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

from eqlib.data import fetch_stock_data, get_price


def generate_chart(result, out_path):
    """
    Generate backtest chart with two panels:
    - Top: price, MA5/MA20, buy/sell markers, holding shading,
      portfolio value (secondary axis), key metrics annotation
    - Bottom: portfolio drawdown (%)
    """
    from eqlib.attribution import analyze_returns

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    analytics = analyze_returns(result)

    # 2-panel figure: price (top, 3/4 height) + drawdown (bottom, 1/4 height)
    fig, (ax, ax_dd) = plt.subplots(
        2, 1, figsize=(16, 10),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    fig.subplots_adjust(hspace=0.05)

    # Fetch price data for the main security
    start = ctx.start_date
    end = ctx.end_date

    securities = set(t["security"] for t in trade_log)
    if not securities and ctx.universe:
        securities.add(ctx.universe[0])
    if not securities:
        securities.add("601390")

    symbol = list(securities)[0]
    df = fetch_stock_data(symbol, start, end)

    if df.empty:
        plt.close()
        return

    dates = df.index.to_numpy()
    closes = df["close"].to_numpy()

    # Price line
    ax.plot(dates, closes, color="#333333", linewidth=1.2, label="Close")

    # MA lines
    ma_fast = df["close"].rolling(5).mean().to_numpy()
    ma_slow = df["close"].rolling(20).mean().to_numpy()
    ax.plot(dates, ma_fast, color="#2196F3", linewidth=1.0, alpha=0.7, label="MA5")
    ax.plot(dates, ma_slow, color="#FF9800", linewidth=1.0, alpha=0.7, label="MA20")

    # Buy/sell markers
    buys = [t for t in trade_log if t["type"] == "BUY"]
    sells = [t for t in trade_log if t["type"] == "SELL"]

    for b in buys:
        ax.annotate(
            "B",
            xy=(b["date"], b["price"]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="circle,pad=0.3", facecolor="#4CAF50", edgecolor="#388E3C"),
        )

    for s in sells:
        ax.annotate(
            "S",
            xy=(s["date"], s["price"]),
            xytext=(0, -12),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="circle,pad=0.3", facecolor="#F44336", edgecolor="#C62828"),
        )

    # Holding period shading
    n_pairs = min(len(buys), len(sells))
    for i in range(n_pairs):
        ax.axvspan(buys[i]["date"], sells[i]["date"],
                   color="#4CAF50", alpha=0.04, zorder=0)

    # Portfolio value on secondary axis
    pf_records = [r for r in recorded if "total_value" in r]
    pf_dates = [r["date"] for r in pf_records]
    pf_values = [r["total_value"] for r in pf_records]

    ax2 = None
    if pf_dates:
        ax2 = ax.twinx()
        ax2.plot(pf_dates, pf_values, color="#9C27B0", linewidth=1.2,
                 alpha=0.6, label="Portfolio")
        ax2.set_ylabel("Portfolio Value", color="#9C27B0", fontsize=10)
        ax2.tick_params(axis="y", labelcolor="#9C27B0")

    # Combine legends from both axes
    handles, labels = ax.get_legend_handles_labels()
    if ax2:
        h2, l2 = ax2.get_legend_handles_labels()
        handles += h2
        labels += l2
    ax.legend(handles, labels, loc="upper left", fontsize=9)

    # Key metrics annotation box (bottom-left corner of price panel)
    if analytics:
        ann_ret = analytics.get("annual_return", 0.0)
        sharpe = analytics.get("sharpe_ratio", 0.0)
        max_dd = analytics.get("max_drawdown", 0.0)
        win = analytics.get("win_rate", 0.0)
        metrics_text = (
            f"Ann.Ret: {ann_ret:+.2%}   Sharpe: {sharpe:.2f}\n"
            f"Max DD: {max_dd:.2%}   Win: {win:.1%}"
        )
        ax.text(
            0.02, 0.04, metrics_text,
            transform=ax.transAxes, fontsize=9,
            verticalalignment="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#cccccc", alpha=0.85),
        )

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    ax.set_title(
        f"{symbol} — PnL: {pnl:+,.2f} ({pnl_pct:+.2f}%)",
        fontsize=13, fontweight="bold",
    )
    ax.set_ylabel("Price", fontsize=10)
    ax.grid(True, alpha=0.25)

    # Drawdown panel
    if pf_dates and pf_values:
        pf_s = pd.Series(pf_values, index=pd.DatetimeIndex(pf_dates))
        rolling_max = pf_s.cummax()
        dd_pct = (pf_s - rolling_max) / rolling_max * 100
        ax_dd.fill_between(
            dd_pct.index, dd_pct.values, 0,
            where=dd_pct.values < 0,
            color="#F44336", alpha=0.35, interpolate=True,
        )
        ax_dd.plot(dd_pct.index, dd_pct.values, color="#F44336", linewidth=0.9)
        ax_dd.axhline(0, color="#555555", linewidth=0.6, linestyle="--")
    ax_dd.set_ylabel("Drawdown (%)", fontsize=10)
    ax_dd.grid(True, alpha=0.25)

    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax_dd.xaxis.set_major_locator(mdates.MonthLocator())
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved: {out_path}")


def generate_report_md(result, out_path):
    """Generate human-readable Markdown report."""
    from eqlib.attribution import analyze_returns

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    symbol = sorted(set(t["security"] for t in trade_log)) or ["N/A"]

    lines = []
    lines.append(f"# Backtest Report: {', '.join(symbol)}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- **Period**: {ctx.start_date} to {ctx.end_date}")
    lines.append(f"- **Initial Capital**: {initial:,.2f}")
    lines.append(f"- **Final Value**: {final:,.2f}")
    pnl_str = f"+{pnl:,.2f}" if pnl >= 0 else f"{pnl:,.2f}"
    pnl_pct_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"
    lines.append(f"- **P&L**: {pnl_str} ({pnl_pct_str})")

    # Count buys and sells
    buy_count = sum(1 for t in trade_log if t["type"] == "BUY")
    sell_count = sum(1 for t in trade_log if t["type"] == "SELL")
    lines.append(f"- **Buy Orders**: {buy_count}")
    lines.append(f"- **Sell Orders**: {sell_count}")
    lines.append("")

    # Risk metrics section
    analytics = analyze_returns(result)
    if analytics:
        lines.append("## Risk Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")

        ann_ret = analytics.get("annual_return", 0.0)
        ann_vol = analytics.get("annual_volatility", 0.0)
        sharpe = analytics.get("sharpe_ratio", 0.0)
        sortino = analytics.get("sortino_ratio", 0.0)
        max_dd = analytics.get("max_drawdown", 0.0)
        dd_start = analytics.get("max_drawdown_start")
        dd_end = analytics.get("max_drawdown_end")
        calmar = analytics.get("calmar_ratio", 0.0)
        alpha = analytics.get("alpha", 0.0)
        beta = analytics.get("beta", 1.0)
        info_ratio = analytics.get("information_ratio", 0.0)
        win_rate = analytics.get("win_rate", 0.0)
        n_days = analytics.get("trading_days", 0)

        dd_period = f"{dd_start} ~ {dd_end}" if dd_start and dd_end else "N/A"

        lines.append(f"| Annual Return | {ann_ret:+.2%} |")
        lines.append(f"| Annual Volatility | {ann_vol:.2%} |")
        lines.append(f"| Sharpe Ratio | {sharpe:.4f} |")
        lines.append(f"| Sortino Ratio | {sortino:.4f} |")
        lines.append(f"| Max Drawdown | {max_dd:.2%} |")
        lines.append(f"| Max DD Period | {dd_period} |")
        lines.append(f"| Calmar Ratio | {calmar:.4f} |")
        lines.append(f"| Alpha (Annual) | {alpha:+.4f} |")
        lines.append(f"| Beta | {beta:.4f} |")
        lines.append(f"| Information Ratio | {info_ratio:.4f} |")
        lines.append(f"| Win Rate (Daily) | {win_rate:.2%} |")
        lines.append(f"| Trading Days | {n_days} |")
        lines.append("")

    # Trade detail
    lines.append("## Trade Log")
    lines.append("")
    if trade_log:
        lines.append("| # | Date | Action | Security | Price | Amount | Commission |")
        lines.append("|---|------|--------|----------|-------|--------|------------|")
        for i, t in enumerate(trade_log, 1):
            action = "BUY" if t["type"] == "BUY" else "SELL"
            comm = f"{t.get('commission', 0):.2f}"
            lines.append(
                f"| {i} | {t['date']} | {action} | {t['security']} "
                f"| {t['price']:.3f} | {t['amount']:,} | {comm} |"
            )
    else:
        lines.append("No trades executed.")
    lines.append("")

    # Portfolio summary
    lines.append("## Positions")
    lines.append("")
    if ctx.portfolio.positions:
        for sec, pos in ctx.portfolio.positions.items():
            if pos.amount > 0:
                lines.append(f"- **{sec}**: {pos.amount} shares, avg_cost={pos.avg_cost:.3f}")
    else:
        lines.append("Flat (no positions).")
    lines.append("")

    # Portfolio value stats
    pf_values = [r.get("total_value") for r in recorded if "total_value" in r]
    if pf_values:
        lines.append("## Portfolio Value")
        lines.append("")
        lines.append(f"- **Observations**: {len(pf_values)}")
        lines.append(f"- **Start**: {pf_values[0]:,.2f}  ({recorded[0]['date']})")
        lines.append(f"- **End**: {pf_values[-1]:,.2f}  ({recorded[-1]['date']})")
        lines.append(f"- **Peak**: {max(pf_values):,.2f}")
        lines.append(f"- **Trough**: {min(pf_values):,.2f}")
        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report saved: {out_path}")


def generate_report_json(result, out_path):
    """Generate machine-readable JSON report."""
    from eqlib.attribution import analyze_returns

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    # Serialize analytics; convert date objects to strings
    analytics = analyze_returns(result)
    analytics_out: dict = {}
    if analytics:
        for k, v in analytics.items():
            if hasattr(v, "isoformat"):
                analytics_out[k] = v.isoformat()
            else:
                analytics_out[k] = v

    report = {
        "symbol": sorted(set(t["security"] for t in trade_log)) or ["N/A"],
        "start_date": str(ctx.start_date),
        "end_date": str(ctx.end_date),
        "initial_capital": initial,
        "final_value": round(final, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "num_trades": len(trade_log),
        "analytics": analytics_out,
        "trades": [
            {
                "type": t["type"],
                "date": str(t["date"]),
                "security": t["security"],
                "price": t["price"],
                "amount": t["amount"],
                "commission": t.get("commission", 0),
            }
            for t in trade_log
        ],
        "positions": {
            sec: {
                "amount": pos.amount,
                "avg_cost": pos.avg_cost,
                "total_value": pos.total_value,
            }
            for sec, pos in ctx.portfolio.positions.items()
            if pos.amount > 0
        },
        "recorded_values": [
            {k: (str(v) if isinstance(v, (datetime.date, datetime.datetime)) else v)
             for k, v in r.items()}
            for r in recorded
        ],
    }

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Data saved: {out_path}")
