"""Example 7: Extended data APIs — financials, constituents, minute-level, tick.

Demonstrates eqlib advanced data capabilities:
1. get_financial_abstract — financial statement summary
2. get_financial_screen — screen stocks by financial metrics
3. get_index_stocks — index constituent stocks
4. get_industry_list / get_industry_stocks — industry boards and constituents
5. fetch_minute_data / get_price_minute — minute-level K-line data
6. get_tick_data — intraday tick data
"""

from eqlib import *


# ============================================================
# Demo 1: Financial data
# ============================================================

def demo_financial():
    """Demonstrate financial data retrieval."""
    log.info("=== Demo: Financial Data ===\n")

    # 1) Financial abstract for a single stock
    log.info("1) Financial abstract for 601390:")
    df = get_financial_abstract("601390")
    if not df.empty:
        dates = list(df.columns[:3])
        log.info(f"   {len(df)} metrics across {len(df.columns)} reporting periods")
        log.info(f"   Latest periods: {dates}")
    print()

    # 2) Screen by financial metrics
    log.info("2) Screening stocks with PE between 5 and 20:")
    screened = get_financial_screen(min_pe=5, max_pe=20)
    if not screened.empty:
        log.info(f"   Found {len(screened)} stocks matching criteria")
        top5 = screened.nsmallest(5, "pe")
        for _, row in top5.iterrows():
            log.info(f"   {row['code']} {row['name']}: PE={row['pe']:.1f}, price={row['price']:.2f}")
    print()


# ============================================================
# Demo 2: Index / industry constituents
# ============================================================

def demo_constituents():
    """Demonstrate index and industry constituents."""
    log.info("=== Demo: Index / Industry Constituents ===\n")

    # 1) Index constituents
    log.info("1) CSI 300 (000300) constituents:")
    constituents = get_index_stocks("000300")
    if not constituents.empty:
        log.info(f"   Total constituents: {len(constituents)}")
        log.info(f"   First 5: {constituents.head(5)[['code', 'name']].to_dict('records')}")
    print()

    # 2) Industry list
    log.info("2) Industry boards:")
    industries = get_industry_list()
    log.info(f"   Total industry boards: {len(industries)}")
    log.info(f"   First 10: {industries[:10]}")
    print()

    # 3) Industry constituents
    if industries:
        target = industries[0]
        log.info(f"3) Constituents of '{target}':")
        ind_stocks = get_industry_stocks(target)
        if not ind_stocks.empty:
            log.info(f"   Total stocks: {len(ind_stocks)}")
            cols = ["code", "name", "price"]
            if "pe" in ind_stocks.columns:
                cols.append("pe")
            available_cols = [c for c in cols if c in ind_stocks.columns]
            log.info(f"   Top 5:\n{ind_stocks[available_cols].head().to_string()}")
    print()


# ============================================================
# Demo 3: Minute-level K-line data
# ============================================================

def demo_minute_data():
    """Demonstrate minute-level data retrieval."""
    log.info("=== Demo: Minute-level K-line ===\n")

    # 1) 5-minute bars
    log.info("1) 5-minute bars for 601390:")
    df = fetch_minute_data("601390", period="5m")
    if not df.empty:
        log.info(f"   Total bars: {len(df)}")
        log.info(f"   Time range: {df.index[0]} ~ {df.index[-1]}")
        log.info(f"   Columns: {list(df.columns)}")
        log.info(f"   Latest 3:\n{df.tail(3).to_string()}")
    print()

    # 2) 1-minute bars
    log.info("2) 1-minute bars for 601318:")
    df = fetch_minute_data("601318", period="1m")
    if not df.empty:
        log.info(f"   Total bars: {len(df)}")
        log.info(f"   Time range: {df.index[0]} ~ {df.index[-1]}")
    print()

    # 3) Multi-stock minute data
    log.info("3) Multi-stock 5-minute data:")
    frames = get_price_minute(["601390", "000001"], count=10, period="5m")
    for code, frame in frames.items():
        log.info(f"   {code}: {len(frame)} bars")
    print()


# ============================================================
# Demo 4: Tick data
# ============================================================

def demo_tick():
    """Demonstrate tick data retrieval."""
    log.info("=== Demo: Tick Data ===\n")

    log.info("Fetching intraday tick data for 601390:")
    df = get_tick_data("601390")
    if not df.empty:
        log.info(f"   Total ticks: {len(df)}")
        log.info(f"   Columns: {list(df.columns)}")
        log.info(f"   First 5:\n{df.head(5).to_string()}")
        log.info(f"   Last 5:\n{df.tail(5).to_string()}")
    else:
        log.info("   No data available (non-trading day or after-hours)")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    demo_financial()
    print()

    demo_constituents()
    print()

    demo_minute_data()
    print()

    demo_tick()
