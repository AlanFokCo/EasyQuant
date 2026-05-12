"""Regenerate HTML report screenshots for all example strategies.

Runs each example script to produce a fresh HTML report, then uses
Playwright to screenshot the charts section (up to daily returns,
excluding trade detail / calendar tables below).

Usage:
    PYTHONPATH=. python tools/regen_screenshots.py
"""
import os
import glob
import time
import subprocess
import sys

SCREENSHOT_MAP = [
    # (example_script, screenshot_filename, working_dir)
    # working_dir is relative to repo root; None = repo root
    ("examples/14_bollinger_strategy.py",       "example_report_html_bollinger.png",        None),
    ("examples/15_macd_volume_strategy.py",      "example_report_html_macd_volume.png",      None),
    ("examples/16_multi_factor_strategy.py",     "example_report_html_multifactor.png",      None),
    ("examples/17_grid_trading_strategy.py",     "example_report_html_grid.png",             None),
    ("examples/19_local_data_backtest.py",       "example_report_html_19_localdata.png",     None),
    ("examples/20_sr_strategy/run_backtest.py",  "example_report_html_sr_strategy.png",      "examples/20_sr_strategy"),
    ("examples/22_stock_selection_strategy.py",  "example_report_html_stock_selection.png",  None),
    ("examples/12_portfolio_backtest.py",        "example_report_html_portfolio.png",        None),
]

OUTPUT_DIR = "tutorials/assets"
SCREENSHOT_HEIGHT = 1800  # px — covers K-line through daily returns
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 900


def find_latest_html(pattern="reports/backtest_*.html"):
    """Find the most recently modified HTML report matching glob."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def run_example(script, work_dir=None):
    """Run an example script and return the latest HTML report path."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cwd = work_dir if work_dir else os.getcwd()
    print(f"\n▶ Running {script} (cwd={cwd})...")
    result = subprocess.run(
        [sys.executable, script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    # Show last few lines of output
    lines = result.stdout.strip().split("\n")
    for line in lines[-6:]:
        print(f"    {line}")
    if result.returncode != 0:
        print(f"    STDERR: {result.stderr[-500:]}")
        return None

    # Find the HTML report
    if work_dir:
        pattern = os.path.join(work_dir, "reports", "backtest_*.html")
    else:
        pattern = "reports/backtest_*.html"
    return find_latest_html(pattern)


def screenshot_html(html_path, screenshot_name):
    """Use Playwright to screenshot the charts section of an HTML report."""
    from playwright.sync_api import sync_playwright

    out_path = os.path.join(OUTPUT_DIR, screenshot_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        page.goto(f"file://{os.path.abspath(html_path)}")
        # Wait for charts to render
        page.wait_for_timeout(3000)

        # Screenshot only the returns section (charts down to daily returns)
        # Strategy: screenshot from top of page to just past daily returns chart
        page.evaluate("""() => {
            // Hide the trade detail / calendar / position sections at the bottom
            const el = document.getElementById('trade-section');
            if (el) el.style.display = 'none';
            const cal = document.getElementById('calendar');
            if (cal) cal.style.display = 'none';
            const pos = document.getElementById('positions');
            if (pos) pos.style.display = 'none';
            const metrics = document.getElementById('metrics-table-section');
            if (metrics) metrics.style.display = 'none';
        }""")
        page.wait_for_timeout(500)

        # Take a full-page screenshot, then we'll clip it
        page.screenshot(path=out_path, full_page=False)
        browser.close()

    print(f"  ✓ Screenshot saved: {out_path}")
    return out_path


def main():
    print("=" * 60)
    print("Regenerating HTML report screenshots")
    print("=" * 60)

    success = 0
    failed = []

    for script, screenshot_name, work_dir in SCREENSHOT_MAP:
        html_path = run_example(script, work_dir)
        if html_path is None:
            failed.append((script, "no HTML report found"))
            continue

        print(f"  HTML report: {html_path}")
        try:
            screenshot_html(html_path, screenshot_name)
            success += 1
        except Exception as e:
            failed.append((script, str(e)))

    print(f"\n{'=' * 60}")
    print(f"Done: {success} succeeded, {len(failed)} failed")
    for script, err in failed:
        print(f"  ✗ {script}: {err}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
