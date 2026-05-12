"""Take screenshots of existing HTML reports.

Maps each existing HTML report to its screenshot filename, then uses
Playwright to capture the entire page from top down to daily returns,
hiding ONLY the trade-detail, calendar, and positions sections at the bottom.

Usage:
    PYTHONPATH=. python tools/take_screenshots.py
"""
import os
import glob
from playwright.sync_api import sync_playwright

SCREENSHOT_MAP = [
    ("reports/backtest_20260513_000712.html",          "example_report_html_bollinger.png"),
    ("reports/backtest_20260513_000723.html",          "example_report_html_macd_volume.png"),
    ("reports/backtest_20260513_000859.html",          "example_report_html_multifactor.png"),
    ("reports/backtest_20260513_000910.html",          "example_report_html_grid.png"),
    ("reports/backtest_20260513_000934.html",          "example_report_html_19_localdata.png"),
    ("reports/backtest_20260513_001351.html",          "example_report_html_sr_strategy.png"),
    ("reports/backtest_20260513_000042.html",          "example_report_html_stock_selection.png"),
    ("reports/backtest_20260513_002121_momentum_v2.html", "example_report_html_portfolio.png"),
]

OUTPUT_DIR = "tutorials/assets"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 900


def screenshot_html(html_path, screenshot_name):
    """Use Playwright to screenshot the full page except trade/calendar/positions."""
    out_path = os.path.join(OUTPUT_DIR, screenshot_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        page.goto(f"file://{os.path.abspath(html_path)}")
        page.wait_for_timeout(3000)

        # Hide bottom-only sections; keep everything from top through daily returns
        page.evaluate("""() => {
            const ids = ['trade-section', 'trade-detail', 'trade-detail-table',
                         'calendar', 'calendar-table', 'positions', 'positions-table'];
            ids.forEach(function(id) {
                const el = document.getElementById(id);
                if (el) { el.style.display = 'none'; el.style.height = '0'; el.style.overflow = 'hidden'; }
            });
            // Also try to hide any parent divs that wrap these
            document.querySelectorAll('.section, .card, .tab').forEach(function(sec) {
                if (sec.textContent.indexOf('成交') > -1 ||
                    sec.textContent.indexOf('日历') > -1 ||
                    sec.textContent.indexOf('持仓') > -1) {
                    sec.style.display = 'none';
                }
            });
        }""")
        page.wait_for_timeout(1000)

        # Full-page screenshot captures from top down through the last visible element
        page.screenshot(path=out_path, full_page=True)
        browser.close()

    print(f"  Screenshot saved: {out_path}")
    return out_path


def main():
    print("Taking screenshots of existing HTML reports...")

    success = 0
    failed = []

    for html_path, screenshot_name in SCREENSHOT_MAP:
        if not os.path.exists(html_path):
            failed.append((html_path, "file not found"))
            print(f"  NOT FOUND: {html_path}")
            continue

        print(f"  Report: {html_path}")
        try:
            screenshot_html(html_path, screenshot_name)
            success += 1
        except Exception as e:
            failed.append((html_path, str(e)))

    print(f"\nDone: {success} succeeded, {len(failed)} failed")
    for path, err in failed:
        print(f"  FAIL: {path}: {err}")


if __name__ == "__main__":
    main()
