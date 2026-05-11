#!/usr/bin/env python3
"""Take screenshots of HTML reports for README preview.
Uses Playwright headless Chromium — no GUI needed.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent
REPORTS_DIR = ROOT / "reports"
ASSETS_DIR = ROOT / "tutorials" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# output filename -> html report file (relative to reports/)
SCREENSHOTS = [
    ("example_report_html_macd_volume.png",  "backtest_20260511_234059_15_macd_volume.html"),
    ("example_report_html_bollinger.png",     "backtest_20260511_233809_14_bollinger.html"),
    ("example_report_html_sr_strategy.png",   "examples/20_sr_strategy/sr_backtest.html"),
    ("example_report_html_grid.png",          "backtest_20260511_234158_17_grid.html"),
    ("example_report_html_multifactor.png",   "backtest_20260511_234455_16_multifactor.html"),
    ("example_report_html_stock_selection.png","backtest_20260512_000211_22_stockselection.html"),
    ("example_report_html_portfolio.png",     "backtest_20260511_235942_momentum_v2_12_portfolio.html"),
    ("example_report_html_19_localdata.png",  "backtest_20260511_234245_19_localdata.html"),
]

# Check sr_backtest.html lives under examples/, not reports/
sr_html = ROOT / "examples" / "20_sr_strategy" / "sr_backtest.html"

def screenshot(html_path: Path, out_path: Path):
    url = html_path.as_uri()
    code = f'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_viewport_size({{"width": 1400, "height": 1000}})
    page.goto("{url}", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    page.screenshot(path="{out_path}", full_page=True)
    browser.close()
'''
    subprocess.run([sys.executable, "-c", code], check=True)

print("=== HTML Report Screenshots ===")
for out_name, html_rel in SCREENSHOTS:
    if "sr_backtest" in html_rel:
        html_path = sr_html
    else:
        html_path = REPORTS_DIR / html_rel
    if not html_path.exists():
        print(f"SKIP (not found): {html_path}")
        continue
    out_path = ASSETS_DIR / out_name
    print(f"  {html_rel} -> {out_name}")
    screenshot(html_path, out_path)
    print(f"  Done: {out_path}  ({out_path.stat().st_size // 1024} KB)")

print("\n=== Done ===")
