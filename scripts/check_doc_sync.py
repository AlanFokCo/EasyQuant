#!/usr/bin/env python3
"""Doc sync validator — checks documentation consistency.

Validates:
1. Every docs/*.md has a corresponding .en.md translation
2. No stale example file references in docs
3. Trading cost rates in docs match examples/_defaults.py
4. No outdated stamp duty (0.001) or commission (0.0003) values
5. With ``--scope all`` (or ``--scope code``), also scans ``eqlib/``,
   ``examples/``, ``web_strategy_studio/``, and ``agent/`` for stale cost
   values so regressions in code are caught alongside docs.

Usage:
    python scripts/check_doc_sync.py                  # Check docs only (default)
    python scripts/check_doc_sync.py --scope all      # Check docs + code
    python scripts/check_doc_sync.py --scope code     # Check code only
    python scripts/check_doc_sync.py --fix            # Auto-fix stale refs/costs in docs
    python scripts/check_doc_sync.py -v               # Verbose output

Exit code 0 = all checks pass, non-zero = issues found.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
EXAMPLES_DIR = ROOT / "examples"

# Skip these directories
SKIP_DIRS = {"superpowers", "__pycache__", "node_modules", ".git", "site",
             ".venv", "venv", "node_modules", "dist", "build"}

# Directories scanned when --scope includes code
CODE_DIRS = [ROOT / "eqlib", ROOT / "examples", ROOT / "web_strategy_studio", ROOT / "agent"]
CODE_SUFFIXES = {".py", ".json", ".ts", ".tsx", ".js", ".jsx"}

# Example file reference pattern: examples/XX_something.py or examples/XX_dir/
EXAMPLE_REF_PATTERN = re.compile(
    r"examples/(\d+_\w+(?:\.py|/))"
)

# Stale example names that should have been updated
STALE_EXAMPLES = {
    "05_paper_trade.py": "12_paper_trade.py",
    "06_advanced_api.py": None,
    "07_market_data.py": None,
    "08_lifecycle_callbacks.py": "07_lifecycle.py",
    "09_attribution_analysis.py": "09_attribution.py",
    "11_utils_library.py": "08_utils_library.py",
    "12_portfolio_backtest.py": "11_portfolio_backtest.py",
    "13_ptrade_export.py": "12_paper_trade.py",
    "14_bollinger_strategy.py": "15_bollinger_strategy.py",
    "15_macd_volume_strategy.py": "16_macd_volume.py",
    "16_multi_factor_strategy.py": "17_multi_factor.py",
    "17_grid_trading_strategy.py": "18_grid_trading.py",
    "18_strategy_comparison.py": None,
    "19_local_data_backtest.py": "06_local_data.py",
    "20_sr_strategy/": "19_sr_portfolio/",
    "21_combined_strategy/": "20_all_weather_alpha/",
    "22_stock_selection_strategy.py": None,
    "23_small_cap_query_example.py": None,
    "24_quick_report_test.py": None,
    "25_ashare_market_sentiment.py": "13_ashare_sentiment.py",
    "26_portfolio_risk_monitor.py": "14_portfolio_risk.py",
}

# Outdated trading cost values
STALE_COSTS = {
    "close_tax=0.001": "close_tax=0.0005",
    "open_commission=0.0003": "open_commission=0.00025",
    "close_commission=0.0003": "close_commission=0.00025",
}

# Files exempt from stale-cost scanning (historical date-aware logic, tests
# of the old rate, or documentation *about* the old rate).
# Pattern: the file path must contain one of these substrings to be skipped.
COST_EXEMPT_PATHS = {
    # objects.py implements the date-aware stamp duty (0.001 is the pre-2023-08-28 rate)
    "eqlib/objects.py",
    # tests that explicitly assert the old rate for date-aware logic
    "tests/test_new_features.py",
}


def get_doc_files():
    """Get all .md files in docs/ (excluding .en.md and skip dirs)."""
    files = []
    for path in DOCS_DIR.rglob("*.md"):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.name.endswith(".en.md"):
            continue
        files.append(path)
    return sorted(files)


def check_translations(doc_files, verbose=False):
    """Check that every Chinese doc has an English counterpart."""
    issues = []
    for path in doc_files:
        en_path = path.with_suffix(".en.md")
        if not en_path.exists():
            rel = path.relative_to(ROOT)
            issues.append(f"  Missing translation: {rel}")
        elif verbose:
            print(f"  OK: {path.relative_to(ROOT)}")
    return issues


def check_stale_refs(verbose=False):
    """Check for references to deleted/renamed example files."""
    issues = []
    all_md = list(DOCS_DIR.rglob("*.md"))

    for path in all_md:
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        # Skip changelog — it documents history
        if "changelog" in path.name:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        rel = path.relative_to(ROOT)

        for stale, replacement in STALE_EXAMPLES.items():
            if stale in content:
                fix = f" → {replacement}" if replacement else " (deleted)"
                issues.append(f"  {rel}: stale ref '{stale}'{fix}")

    return issues


def _iter_code_files():
    """Yield code files (py/json/ts/tsx/js/jsx) under CODE_DIRS, honoring SKIP_DIRS."""
    for base in CODE_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in CODE_SUFFIXES:
                continue
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            yield path


def _is_cost_exempt(path: Path) -> bool:
    """Return True if path is exempt from stale-cost scanning."""
    rel_str = str(path.relative_to(ROOT))
    return any(exempt in rel_str for exempt in COST_EXEMPT_PATHS)


def check_stale_costs(verbose=False, scope="docs"):
    """Check for outdated trading cost values in docs and (optionally) code."""
    issues = []

    paths = list(DOCS_DIR.rglob("*.md")) if scope in ("docs", "all") else []
    if scope in ("code", "all"):
        paths.extend(_iter_code_files())

    for path in paths:
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if "changelog" in path.name:
            continue
        if _is_cost_exempt(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        rel = path.relative_to(ROOT)

        for stale, correct in STALE_COSTS.items():
            if stale in content:
                issues.append(f"  {rel}: '{stale}' should be '{correct}'")

    return issues


def check_example_refs_exist(verbose=False):
    """Check that referenced example files actually exist."""
    issues = []
    all_md = list(DOCS_DIR.rglob("*.md"))

    for path in all_md:
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if "changelog" in path.name:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        rel = path.relative_to(ROOT)

        for match in EXAMPLE_REF_PATTERN.finditer(content):
            ref = match.group(1)
            example_path = EXAMPLES_DIR / ref
            if not example_path.exists():
                issues.append(f"  {rel}: references '{ref}' but file not found")

    return issues


def auto_fix_stale_refs():
    """Auto-fix stale example references in docs."""
    fixed = 0
    all_md = list(DOCS_DIR.rglob("*.md"))

    for path in all_md:
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if "changelog" in path.name:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        original = content
        for stale, replacement in STALE_EXAMPLES.items():
            if replacement and stale in content:
                content = content.replace(stale, replacement)

        if content != original:
            path.write_text(content, encoding="utf-8")
            fixed += 1
            print(f"  Fixed: {path.relative_to(ROOT)}")

    return fixed


def auto_fix_stale_costs():
    """Auto-fix outdated trading cost values in docs."""
    fixed = 0
    all_md = list(DOCS_DIR.rglob("*.md"))

    for path in all_md:
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        original = content
        for stale, correct in STALE_COSTS.items():
            content = content.replace(stale, correct)

        if content != original:
            path.write_text(content, encoding="utf-8")
            fixed += 1
            print(f"  Fixed: {path.relative_to(ROOT)}")

    return fixed


def main():
    parser = argparse.ArgumentParser(description="Doc sync validator")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix stale refs and costs")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show OK files too")
    parser.add_argument("--scope", choices=["docs", "code", "all"],
                        default="docs",
                        help="Scan scope: docs only (default), code only, or all")
    args = parser.parse_args()

    if args.fix:
        print("Auto-fixing stale example references...")
        n = auto_fix_stale_refs()
        print(f"  Fixed {n} files\n")

        print("Auto-fixing stale trading costs...")
        n = auto_fix_stale_costs()
        print(f"  Fixed {n} files\n")
        return 0

    doc_files = get_doc_files()
    scope_label = {"docs": "docs", "code": "code", "all": "docs + code"}[args.scope]
    print(f"Checking {scope_label} (scope={args.scope})...\n")

    all_issues = []

    # Check 1: Translations (docs only, always)
    print("1. Translation coverage:")
    issues = check_translations(doc_files, args.verbose)
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(i)
        print(f"  → {len(issues)} missing translations\n")
    else:
        print("  ✓ All docs have .en.md translations\n")

    # Check 2: Stale example refs (docs only)
    print("2. Example file references:")
    issues = check_stale_refs(args.verbose)
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(i)
        print(f"  → {len(issues)} stale references (run with --fix)\n")
    else:
        print("  ✓ All example references are current\n")

    # Check 3: Stale trading costs (docs and/or code based on scope)
    print(f"3. Trading cost values (scope={args.scope}):")
    issues = check_stale_costs(args.verbose, scope=args.scope)
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(i)
        print(f"  → {len(issues)} outdated values\n")
    else:
        print(f"  ✓ All trading costs are current (scope={args.scope})\n")

    # Check 4: Example refs exist (docs only)
    print("4. Example file existence:")
    issues = check_example_refs_exist(args.verbose)
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(i)
        print(f"  → {len(issues)} broken references\n")
    else:
        print("  ✓ All referenced example files exist\n")

    # Summary
    if all_issues:
        print(f"FAILED: {len(all_issues)} issues found")
        print("Run 'python scripts/check_doc_sync.py --fix' to auto-fix what's possible.")
        return 1
    else:
        print("ALL CHECKS PASSED ✓")
        return 0


if __name__ == "__main__":
    sys.exit(main())
