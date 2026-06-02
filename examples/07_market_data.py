"""Example 7: Extended data APIs — financials, constituents, minute-level, tick, A-share specific data.

Demonstrates eqlib advanced data capabilities:
1. get_financial_abstract — financial statement summary
2. get_financial_screen — screen stocks by financial metrics
3. get_index_stocks — index constituent stocks
4. get_industry_list / get_industry_stocks — industry boards and constituents
5. fetch_minute_data / get_price_minute — minute-level K-line data
6. get_tick_data — intraday tick data
7. get_north_money_flow — north-bound capital flow (沪股通+深股通汇总)
8. get_margin_data — margin trading data (融资融券)
9. get_limit_up_down_stats — daily limit up/down statistics
10. get_restriction_release — restricted share release schedule
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
# Demo 5: A-share market specific data
# ============================================================

def demo_ashare_data():
    """A 股特色数据：北向资金、融资融券、涨跌停、限售股解禁。"""
    log.info("=== Demo: A-share Market Specific Data ===\n")

    # 1) 北向资金流向
    log.info("1) 北向资金流向（近 3 个月）:")
    north = get_north_money_flow(start_date="2024-01-01", end_date="2024-03-31")
    if not north.empty:
        log.info(f"   Total records: {len(north)}")
        log.info(f"   Columns: {list(north.columns)}")
        log.info(f"   Latest 5 days:\n{north.tail(5).to_string()}")
        # 计算近 5 日净买入
        recent_5d = north["net_buy"].tail(5).sum()
        log.info(f"   近 5 日净买入合计: {recent_5d:.2f} 亿元")
    else:
        log.info("   No data available")
    print()

    # 2) 融资融券
    log.info("2) 融资融券数据（近 3 个月）:")
    margin = get_margin_data(start_date="2024-01-01", end_date="2024-03-31")
    if not margin.empty:
        log.info(f"   Total records: {len(margin)}")
        log.info(f"   Columns: {list(margin.columns)}")
        log.info(f"   Latest 5 days:\n{margin.tail(5).to_string()}")
        # 计算融资余额变化
        if len(margin) >= 5:
            balance_change = margin["margin_balance"].iloc[-1] - margin["margin_balance"].iloc[-5]
            log.info(f"   近 5 日融资余额变化: {balance_change:.2f} 亿元")
    else:
        log.info("   No data available")
    print()

    # 3) 涨跌停统计
    log.info("3) 涨跌停统计（近 30 天）:")
    limit_stats = get_limit_up_down_stats()
    if not limit_stats.empty:
        log.info(f"   Total records: {len(limit_stats)}")
        log.info(f"   Columns: {list(limit_stats.columns)}")
        log.info(f"   Latest 10 days:\n{limit_stats.tail(10).to_string()}")
        # 计算涨跌停比值
        if len(limit_stats) > 0:
            latest = limit_stats.iloc[-1]
            ratio = latest["limit_up_count"] / max(latest["limit_down_count"], 1)
            log.info(f"   最新一日涨跌停比值: {ratio:.2f}")
    else:
        log.info("   No data available")
    print()

    # 4) 限售股解禁
    log.info("4) 限售股解禁（未来 30 天）:")
    releases = get_restriction_release(days=30)
    if not releases.empty:
        log.info(f"   Total upcoming releases: {len(releases)}")
        log.info(f"   Columns: {list(releases.columns)}")
        # 按解禁市值排序，显示前 10
        if "release_value" in releases.columns:
            top_releases = releases.nlargest(10, "release_value")
            log.info(f"   Top 10 by release value:\n{top_releases.to_string()}")
        else:
            log.info(f"   First 10:\n{releases.head(10).to_string()}")
    else:
        log.info("   No data available")


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
    print()

    demo_ashare_data()
