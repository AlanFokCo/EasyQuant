"""Example 10: Index and concept-based strategies.

Demonstrates:
- Building strategy universes from index constituents
- Concept/theme board strategies
- get_index_weights for weighted allocation
- get_industry / get_concept_list / get_concept_stocks

Usage:
    python examples/10_index_concept.py
"""

from eqlib import *


# ============================================================
# Strategy: Index momentum with concept filter
# ============================================================

def initialize(context):
    """Initialize index-based strategy."""
    g.index_code = "000300"
    g.max_stocks = 10
    g.lookback = 20

    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5,
    ))

    # Build universe from index constituents
    index_df = get_index_stocks(g.index_code)
    if not index_df.empty:
        context.universe = index_df["code"].head(g.max_stocks).tolist()
        log.info(f"Universe: top {len(context.universe)} from {g.index_code}")

    run_weekly(rebalance, day_of_week=0, time="09:30")


def rebalance(context):
    """Weekly rebalance based on momentum."""
    universe = context.universe
    if not universe:
        return

    # Score stocks by momentum
    scores = {}
    for sec in universe:
        df = attribute_history(sec, g.lookback + 5, "1d", ["close"])
        if df.empty or len(df) < g.lookback:
            continue
        ret = (df["close"].iloc[-1] / df["close"].iloc[-g.lookback]) - 1
        scores[sec] = ret

    if not scores:
        return

    # Buy top N by momentum
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    picks = [s[0] for s in sorted_stocks[:g.max_stocks]]

    # Sell non-picks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in picks:
            order_target(sec, 0)

    # Buy picks
    per_stock = context.portfolio.available_cash / len(picks)
    for sec in picks:
        if per_stock > 1000:
            order_value(sec, per_stock)

    record(total_value=context.portfolio.total_value)


def demo_index_concepts():
    """Demo index and concept data APIs."""
    log.info("=== Index & Concept Data Demo ===\n")

    # Index constituents
    log.info("1) CSI 300 constituents (top 5):")
    idx = get_index_stocks("000300")
    if not idx.empty:
        log.info(f"   Total: {len(idx)}")
        log.info(f"   {idx.head(5).to_dict('records')}")

    # Index weights
    log.info("\n2) CSI 300 weights (top 5):")
    w = get_index_weights("000300")
    if not w.empty and "weight" in w.columns:
        top5 = w.nlargest(5, "weight")
        log.info(f"   {top5.to_dict('records')}")

    # Concept list
    log.info("\n3) Concept boards (first 10):")
    concepts = get_concept_list()
    if concepts:
        log.info(f"   Total: {len(concepts)}")
        log.info(f"   {concepts[:10]}")

    # Industry classification
    log.info("\n4) Industry info for 601390:")
    info = get_industry("601390")
    if info:
        log.info(f"   {info}")


if __name__ == "__main__":
    demo_index_concepts()
    print()

    # Run backtest
    import datetime

    idx = get_index_stocks("000300")
    preload = (
        idx["code"].head(10).tolist()
        if not idx.empty
        else ["601390", "600519", "000001", "600036", "000858"]
    )

    result = run_backtest(
        initialize_func=initialize,
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2024, 6, 30),
        starting_cash=100000,
        securities=preload,
        use_local=True,
    )

    if result is not None:
        ctx = result["context"]
        print(f"\n{'=' * 60}")
        print(f"Final value: {ctx.portfolio.total_value:,.2f}")
        print(f"Trades: {len(result['trade_log'])}")
        for sec, pos in ctx.portfolio.positions.items():
            if pos.amount > 0:
                print(f"  Position: {sec} - {pos.amount} shares")
