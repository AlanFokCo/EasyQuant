"""Report generation: chart (PNG), JSON, and Markdown."""

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


def generate_chart(result, out_path):
    """
    Generate backtest chart with price, MA lines, buy/sell markers,
    and holding period shading.
    """
    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    fig, ax = plt.subplots(figsize=(16, 8))

    # Fetch all data for charting
    start = ctx.start_date
    end = ctx.end_date

    # Get the main security (first in universe or first traded)
    securities = set()
    for t in trade_log:
        securities.add(t["security"])
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
    buys = []
    sells = []
    for t in trade_log:
        if t["type"] == "BUY":
            buys.append(t)
        elif t["type"] == "SELL":
            sells.append(t)

    for b in buys:
        ax.annotate(
            "BUY",
            xy=(b["date"], b["price"]),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="circle,pad=0.25", facecolor="green", edgecolor="darkgreen"),
        )

    for s in sells:
        ax.annotate(
            "SELL",
            xy=(s["date"], s["price"]),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="circle,pad=0.25", facecolor="red", edgecolor="darkred"),
        )

    # Holding period shading
    n_pairs = min(len(buys), len(sells))
    for i in range(n_pairs):
        ax.axvspan(buys[i]["date"], sells[i]["date"],
                   color="green", alpha=0.05, zorder=0)

    # Portfolio value on secondary axis
    if recorded:
        rec_dates = [r["date"] for r in recorded]
        if "total_value" in recorded[0]:
            values = [r.get("total_value", 0) for r in recorded]
            ax2 = ax.twinx()
            ax2.plot(rec_dates, values, color="#4CAF50", linewidth=0.8,
                     alpha=0.5, label="Portfolio Value")
            ax2.set_ylabel("Portfolio Value", color="#4CAF50")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    ax.set_title(
        f"{symbol} Backtest: PnL={pnl:+.2f} ({pnl_pct:+.2f}%)",
        fontsize=14,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Chart saved: {out_path}")


def generate_report_md(result, out_path):
    """Generate human-readable Markdown report."""
    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    symbol = list(set(t["security"] for t in trade_log) or ["N/A"])

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

    # Recorded values
    if recorded:
        lines.append("## Portfolio Values")
        lines.append("")
        lines.append(f"{len(recorded)} data points recorded.")
        if recorded:
            first = recorded[0]
            last = recorded[-1]
            lines.append(f"- Start: {first['date']}")
            lines.append(f"- End: {last['date']}")
        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report saved: {out_path}")


def generate_report_json(result, out_path):
    """Generate machine-readable JSON report."""
    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial) * 100

    report = {
        "symbol": list(set(t["security"] for t in trade_log) or ["N/A"]),
        "start_date": str(ctx.start_date),
        "end_date": str(ctx.end_date),
        "initial_capital": initial,
        "final_value": round(final, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "num_trades": len(trade_log),
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
