"""
10 - Index, Industry & Concept Boards
======================================

Demonstrates A-share index and classification APIs:
- get_index_stocks(): constituents of an index (e.g., CSI 300)
- get_index_weights(): constituent stock weights
- get_concept_list(): all concept/theme board names
- get_concept_stocks(): stocks in a concept board
- get_industry_list(): all industry sector names
- get_industry_stocks(): stocks in an industry
- get_industry(): industry details for a stock

Also includes a simple index constituent rotation strategy.

Teaching Objectives:
    - Using index constituents as a stock pool
    - Industry and concept board exploration
    - Weighted portfolio construction from index weights

Expected Output:
    - CSI 300 constituent list and top weights
    - Concept board list and sample stocks
    - Industry classification examples
    - Rotation strategy backtest results

Run:
    python examples/10_index_concept.py
"""

from eqlib import (
    get_index_stocks,
    get_index_weights,
    get_concept_list,
    get_concept_stocks,
    get_industry_list,
    get_industry_stocks,
    get_industry,
    run_backtest,
    set_benchmark,
    set_order_cost,
    run_monthly,
    attribute_history,
    order_value,
    order_target,
    record,
    log,
    g,
)
from examples._defaults import (
    STOCKS,
    STOCKS_TRADE,
    INDEX_HS300,
    DEFAULT_ORDER_COST,
    INITIAL_CASH,
    START_DATE,
    END_DATE,
    verify_data_available,
    print_evaluation,
)


# ============================================================
# Demo 1: Index constituents and weights
# ============================================================

def demo_index_stocks():
    """Show CSI 300 constituents and top-10 weights."""
    print("\n" + "=" * 55)
    print("1) CSI 300 Index Constituents & Weights")
    print("=" * 55)

    # Fetch constituent list
    idx_df = get_index_stocks("000300")
    if idx_df.empty:
        print("  Could not fetch CSI 300 constituents (network issue?).")
        return [], None

    print(f"  Total constituents: {len(idx_df)}")
    print(f"\n  First 10 constituents:")
    print(f"  {'Code':<10} {'Name':<12}")
    print(f"  {'-'*10} {'-'*12}")
    for _, row in idx_df.head(10).iterrows():
        code = row.get("code", "")
        name = row.get("name", "")
        print(f"  {code:<10} {name:<12}")

    # Fetch weights
    w_df = get_index_weights("000300")
    if w_df.empty or "weight" not in w_df.columns:
        print("\n  Could not fetch index weights.")
        return idx_df["code"].tolist(), None

    top10 = w_df.nlargest(10, "weight")
    print(f"\n  Top 10 constituents by weight:")
    print(f"  {'Code':<10} {'Name':<12} {'Weight':>8}")
    print(f"  {'-'*10} {'-'*12} {'-'*8}")
    for _, row in top10.iterrows():
        code = row.get("code", "")
        name = row.get("name", "")
        weight = row.get("weight", 0)
        print(f"  {code:<10} {name:<12} {weight:>7.2f}%")

    return idx_df["code"].tolist(), w_df


# ============================================================
# Demo 2: Concept boards
# ============================================================

def demo_concepts():
    """List all concept boards, show stocks in one concept."""
    print("\n" + "=" * 55)
    print("2) Concept / Theme Boards")
    print("=" * 55)

    concepts = get_concept_list()
    if not concepts:
        print("  Could not fetch concept list (network issue?).")
        return

    print(f"  Total concept boards: {len(concepts)}")
    print(f"\n  First 15 concepts:")
    for i, name in enumerate(concepts[:15], 1):
        print(f"    {i:>3}. {name}")

    # Pick the first concept and show its stocks
    sample = concepts[0]
    print(f"\n  Stocks in concept '{sample}':")
    stocks_df = get_concept_stocks(sample)
    if stocks_df.empty:
        print("    Could not fetch concept stocks.")
        return

    show_n = min(10, len(stocks_df))
    print(f"    Total: {len(stocks_df)} stocks (showing {show_n})")
    print(f"    {'Code':<10} {'Name':<12}")
    print(f"    {'-'*10} {'-'*12}")
    for _, row in stocks_df.head(show_n).iterrows():
        code = row.get("code", "")
        name = row.get("name", "")
        print(f"    {code:<10} {name:<12}")


# ============================================================
# Demo 3: Industry classification
# ============================================================

def demo_industries():
    """List all industries, show stocks in one industry."""
    print("\n" + "=" * 55)
    print("3) Industry Classification")
    print("=" * 55)

    industries = get_industry_list()
    if not industries:
        print("  Could not fetch industry list (network issue?).")
        return

    print(f"  Total industries: {len(industries)}")
    print(f"\n  First 15 industries:")
    for i, name in enumerate(industries[:15], 1):
        print(f"    {i:>3}. {name}")

    # Pick the first industry and show its stocks
    sample = industries[0]
    print(f"\n  Stocks in industry '{sample}':")
    stocks_df = get_industry_stocks(sample)
    if stocks_df.empty:
        print("    Could not fetch industry stocks.")
        return

    show_n = min(10, len(stocks_df))
    print(f"    Total: {len(stocks_df)} stocks (showing {show_n})")
    print(f"    {'Code':<10} {'Name':<12}")
    print(f"    {'-'*10} {'-'*12}")
    for _, row in stocks_df.head(show_n).iterrows():
        code = row.get("code", "")
        name = row.get("name", "")
        print(f"    {code:<10} {name:<12}")

    # Show industry classification for a known stock
    sample_code = STOCKS["liquor"]  # 600519 Moutai
    info = get_industry(sample_code)
    if info:
        print(f"\n  Industry info for {sample_code}:")
        for key, val in info.items():
            print(f"    {key}: {val}")
    else:
        print(f"\n  Could not fetch industry info for {sample_code}.")


# ============================================================
# Demo 4: Rotation strategy backtest
# ============================================================

# Strategy parameters
MOMENTUM_LOOKBACK = 20   # 20-day momentum window
MAX_PICKS = 5            # Buy top-5 stocks each month
UNIVERSE_SIZE = 20       # Pre-load top-20 CSI 300 constituents


def initialize_rotation(context):
    """Initialize the rotation strategy."""
    set_benchmark(INDEX_HS300)
    set_order_cost(DEFAULT_ORDER_COST)

    g.lookback = MOMENTUM_LOOKBACK
    g.max_picks = MAX_PICKS

    # Universe is set from __main__ after fetching CSI 300 constituents
    run_monthly(monthly_rebalance, day_of_month=1, time="09:30")


def monthly_rebalance(context):
    """Monthly rebalance: pick top-N by 20-day momentum."""
    universe = getattr(g, "universe", [])
    if not universe:
        return

    # Score each stock by momentum (20-day return)
    scores = {}
    for sec in universe:
        df = attribute_history(sec, g.lookback + 5, "1d", ["close"])
        if df is None or df.empty or len(df) < g.lookback:
            continue
        ret = (df["close"].iloc[-1] / df["close"].iloc[-g.lookback]) - 1
        scores[sec] = ret

    if not scores:
        log.info("No valid momentum scores this month.")
        return

    # Rank by momentum descending, pick top N
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    picks = [s[0] for s in sorted_stocks[:g.max_picks]]

    log.info("Top picks: %s", picks)

    # Sell positions not in picks
    for sec in list(context.portfolio.positions.keys()):
        if sec not in picks:
            order_target(sec, 0)

    # Equal-weight buy into picks
    per_stock = context.portfolio.available_cash / max(len(picks), 1)
    for sec in picks:
        if per_stock > 1000:
            order_value(sec, per_stock)

    record(total_value=context.portfolio.total_value)


def demo_rotation_strategy(constituent_codes):
    """Run a simple monthly rotation backtest on CSI 300 constituents."""
    print("\n" + "=" * 55)
    print("4) Monthly Momentum Rotation Strategy")
    print("=" * 55)

    if not constituent_codes:
        print("  No constituent codes available — skipping backtest.")
        return

    # Use a manageable subset for preloading
    universe = constituent_codes[:UNIVERSE_SIZE]
    print(f"  Universe: top {len(universe)} CSI 300 constituents")
    print(f"  Strategy: monthly pick top-{MAX_PICKS} by {MOMENTUM_LOOKBACK}-day momentum")

    # Store universe on g for the strategy to access
    g.universe = universe

    actual_start, actual_end = verify_data_available(
        universe[0], START_DATE, END_DATE)

    result = run_backtest(
        initialize_func=initialize_rotation,
        start_date=actual_start,
        end_date=actual_end,
        starting_cash=INITIAL_CASH,
        benchmark=INDEX_HS300,
        securities=universe,
        use_local=True,
    )

    if result is None:
        print("  Backtest failed — no results.")
        return

    ctx = result["context"]
    print(f"\n  Final portfolio value: {ctx.portfolio.total_value:,.2f}")
    print(f"  Total trades: {len(result['trade_log'])}")

    # Show open positions
    if ctx.portfolio.positions:
        print(f"\n  Open positions:")
        for sec, pos in ctx.portfolio.positions.items():
            if pos.amount > 0:
                print(f"    {sec}: {pos.amount} shares @ avg {pos.avg_cost:.2f}")

    print_evaluation(result, "Rotation Strategy")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("10 - Index, Industry & Concept Boards")
    print("=" * 55)

    # Demo 1: Index constituents & weights
    codes, weights_df = demo_index_stocks()

    # Demo 2: Concept boards
    demo_concepts()

    # Demo 3: Industry classification
    demo_industries()

    # Demo 4: Rotation strategy backtest
    demo_rotation_strategy(codes)
