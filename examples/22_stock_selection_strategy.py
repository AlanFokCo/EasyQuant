"""Example 22: Stock Selection Strategy Interface.

Demonstrates the ``run_selection`` / ``selection_func`` API for periodic
portfolio rebalancing with factor-based stock selection.

Three ways to define a selection strategy are shown below.
Pick whichever style fits your workflow best.

Usage:
    python examples/22_stock_selection_strategy.py
"""

from eqlib import *


# ============================================================
# Candidate pool (define here so it survives engine reset)
# ============================================================

CANDIDATE_POOL = [
    "601390",  # ICBC (banking)
    "600519",  # Kweichow Moutai (liquor)
    "000858",  # Wuliangye (liquor)
    "600036",  # China Merchants Bank (banking)
    "000001",  # Ping An Bank (banking)
    "601318",  # Ping An Insurance (insurance)
    "600276",  # Hengrui Pharma (pharma)
    "000333",  # Midea Group (appliances)
    "600887",  # Yili Industrial (dairy)
    "000651",  # Gree Electric (appliances)
    "601166",  # Industrial Bank (banking)
    "002714",  # Muyuan Foods (agriculture)
]
TOP_N = 5
REBALANCE = "monthly:1"


# ============================================================
# Pattern 1: Plain function (simplest, recommended for beginners)
#
# Write a function that takes context and returns a list of codes.
# No class needed — just filter and rank directly.
# ============================================================

def simple_selection(context):
    """Plain function: filter ST, then pick top 5 by lowest PE.

    This is the simplest way to write a selection strategy:
    1. Start with your candidate pool (or context.universe)
    2. Apply filters: remove ST, high PE, etc.
    3. Rank remaining stocks and return top N
    """
    # Step 1: filter — remove ST stocks
    filtered = filter_st_stocks(CANDIDATE_POOL)

    # Step 2: fetch factor data and rank by PE (lowest first)
    df = fetch_factor_data(filtered, fields=["pe"])
    if df.empty or "pe" not in df.columns:
        return context.universe  # fallback to current universe

    df = df.dropna(subset=["pe"])
    df = df.sort_values("pe", ascending=True)
    return df.head(TOP_N).index.tolist()


# ============================================================
# Pattern 2: StockSelector subclass (recommended for complex logic)
#
# Inherit from StockSelector and implement filter() and rank().
# Good when you need reusable selection logic with parameters.
# ============================================================

class LowPEHighMomentumSelector(StockSelector):
    """Select stocks with low PE and positive momentum.

    Parameters:
        top_n: number of stocks to select
        min_momentum: minimum pct_change to qualify
        max_pe: maximum P/E ratio to qualify
    """

    def __init__(self, top_n=5, min_momentum=-3.0, max_pe=80.0):
        self.top_n = top_n
        self.min_momentum = min_momentum
        self.max_pe = max_pe

    def filter(self, candidates, context):
        """Remove unsuitable stocks."""
        # Remove ST stocks
        filtered = filter_st_stocks(candidates)

        # Remove high PE stocks
        filtered = filter_high_pe_stocks(filtered, max_pe=self.max_pe)

        # Remove negative momentum stocks
        df = fetch_factor_data(filtered, fields=["pct_change"])
        if not df.empty and "pct_change" in df.columns:
            filtered = [
                s for s in filtered
                if s in df.index and df.at[s, "pct_change"] > self.min_momentum
            ]

        return filtered

    def rank(self, securities, context):
        """Rank by PE (lowest first) and pick top N."""
        selector = TopNSelector(factor="pe", top_n=self.top_n, ascending=True)
        return selector.rank(securities, context)


# ============================================================
# Pattern 3: Built-in selector (quickest, no code needed)
#
# Use TopNSelector or MultiFactorSelector directly.
# Good for quick experiments and common selection patterns.
# ============================================================

def builtin_selection(context):
    """Use built-in MultiFactorSelector directly.

    Factors:
        -0.4 * PE  (lower PE is better, so negative weight)
        -0.2 * PB  (lower PB is better)
        +0.4 * momentum  (higher pct_change is better)
    """
    selector = MultiFactorSelector(
        factors={"pe": -0.4, "pb": -0.2, "pct_change": 0.4},
        top_n=TOP_N,
    )

    # Filter first, then rank
    candidates = filter_st_stocks(CANDIDATE_POOL)
    candidates = filter_high_pe_stocks(candidates, max_pe=80.0)
    return selector.rank(candidates, context)


# ============================================================
# Trading logic (runs daily, trades the selected universe)
# ============================================================

def initialize(context):
    set_benchmark("000300.XSHG")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ))

    # Initial universe before first selection runs
    context.universe = CANDIDATE_POOL[:6]

    # --- Register selection function (pick one of the three patterns) ---
    run_selection(simple_selection, rebalance=REBALANCE)
    # run_selection(builtin_selection, rebalance=REBALANCE)

    # Or use the StockSelector subclass pattern:
    # selector = LowPEHighMomentumSelector(top_n=TOP_N)
    # def selector_func(ctx):
    #     filtered = selector.filter(CANDIDATE_POOL, ctx)
    #     return selector.rank(filtered, ctx)
    # run_selection(selector_func, rebalance=REBALANCE)

    # Run trading logic every day
    run_daily(trade, time="every_bar")


def trade(context):
    """Equal-weight rebalance based on the current selection.

    This is a common trading pattern for selection strategies:
    1. Sell any position not in the current selection
    2. Equal-weight buy the selected stocks
    """
    selected = context.universe or []
    if not selected:
        return

    # Sell positions not in the selection
    for sec in list(context.portfolio.positions.keys()):
        if sec not in selected:
            pos = context.portfolio.positions[sec]
            if pos.amount > 0 and pos.closeable_amount > 0:
                order_target(sec, 0)
                log.info("SELL %s (not selected)" % sec)

    # Equal-weight buy selected stocks
    n = len(selected)
    if n == 0:
        return

    per_stock_cash = context.portfolio.available_cash / n
    for sec in selected:
        if sec in context.portfolio.positions and \
           context.portfolio.positions[sec].amount > 0:
            continue
        if per_stock_cash < 1000:
            continue
        order_value(sec, per_stock_cash)
        log.info("BUY %s, value=%.0f" % (sec, per_stock_cash))

    # Record
    record(
        total_value=context.portfolio.total_value,
        num_holdings=len([
            s for s, p in context.portfolio.positions.items()
            if p.amount > 0
        ]),
    )


# ============================================================
# Run backtest
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Stock Selection Strategy Interface Demo")
    print("=" * 60)
    print("Candidate pool: %d stocks" % len(CANDIDATE_POOL))
    print("Top picks per rebalance: %d" % TOP_N)
    print("Rebalance frequency: %s" % REBALANCE)
    print()

    result = run_strategy(
        initialize_func=initialize,
        start_date="2024-01-01",
        end_date="2024-12-31",
        starting_cash=200000,
        benchmark="000300.XSHG",
        securities=CANDIDATE_POOL,
        report_dir="reports",
    )

    if result is not None:
        print("\n--- Brinson Attribution ---")
        attribution = brinson_attribution(result)
        if attribution:
            for k, v in attribution.items():
                print(f"  {k}: {v:.4f}")
