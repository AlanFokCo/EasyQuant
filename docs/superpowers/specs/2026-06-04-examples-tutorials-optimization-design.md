# Examples & Tutorials Systematic Optimization Design

**Date**: 2026-06-04
**Status**: Approved
**Scope**: examples/ (31 files) + docs/tutorials/ + docs/how-to/ + docs/reference/
**Approach**: Full rebuild (Clean Slate) with three-tier progressive structure

---

## 1. Goals & Constraints

### 1.1 Primary Goals

1. **Code accuracy** — Every example must run without errors; all data must be obtainable; all strategies must produce valid backtest results
2. **Reproducibility** — Any user following the tutorial or running an example must get consistent, expected results
3. **Scientific rigor** — Strategy choices, parameters, and evaluation metrics must have clear justification; avoid arbitrary or misleading defaults
4. **User friendliness** — Clear learning path from beginner to advanced; consistent code style; helpful error messages
5. **Coverage completeness** — All major eqlib APIs demonstrated; no critical gaps
6. **Content value** — Each example teaches something unique; no redundant copies

### 1.2 Constraints

- English translation is **out of scope** for this iteration
- Core library (`eqlib/`) must **not** be modified
- Must maintain backward compatibility for existing tutorials that reference specific example numbers
- Must not break the MkDocs build or any existing cross-references

---

## 2. Three-Tier Progressive Structure

### 2.1 Foundation Layer (01–07)

**Teaching objective**: Users master EasyQuant basics — from data retrieval to running their first backtest.

| No. | File | Teaching Objective | Source |
|-----|------|-------------------|--------|
| 01 | `01_fetch_data.py` | Data APIs: `get_price`, `fetch_stock_data`, `get_all_securities`, `scan_market` | Rewrite of current 01 |
| 02 | `02_write_strategy.py` | Strategy writing: `initialize`, `handle_data`, `g` object, MA crossover | Rewrite of current 02 |
| 03 | `03_run_backtest.py` | Running backtests: `run_backtest`, trade records, basic metric interpretation | Rewrite of current 03 |
| 04 | `04_stock_screener.py` | Stock screening: `scan_market`, `check_golden_cross`, restriction release filter, `query()` API | Rewrite of current 04 + current 23 |
| 05 | `05_reports.py` | Report generation: PNG/HTML/MD/JSON four formats, metric quick-reference | Rewrite of current 24 + current 09 report section |
| 06 | `06_local_data.py` | Local data: `use_local`, `save_stock_local`, batch download | Rewrite of current 19 |
| 07 | `07_lifecycle.py` | Lifecycle callbacks: `before_trading_start`, `after_trading_end`, `set_universe`, ST detection | Rewrite of current 08 |

### 2.2 Intermediate Layer (08–14)

**Teaching objective**: Master analysis tools, advanced APIs, and A-share specific features.

| No. | File | Teaching Objective | Source |
|-----|------|-------------------|--------|
| 08 | `08_utils_library.py` | Utility library: technical indicators + statistical tools + money management | Rewrite of current 11 |
| 09 | `09_attribution.py` | Attribution analysis: `analyze_returns`, `brinson_attribution`, `simple_factor_analysis` | Rewrite of current 09 |
| 10 | `10_index_concept.py` | Index & industry: `get_index_stocks`, `get_index_weights`, `get_concept_list` | Rewrite of current 10 |
| 11 | `11_portfolio_backtest.py` | Portfolio backtest: `StrategyConfig`, `run_portfolio_backtest` | Rewrite of current 12 |
| 12 | `12_paper_trade.py` | Paper trading: `run_paper_trade`, DingTalk/Feishu notifications, pre-market monitoring | Rewrite of current 05 |
| 13 | `13_ashare_sentiment.py` | A-share sentiment: north-bound capital + margin + limit up/down + restriction release composite | Rewrite of current 25 |
| 14 | `14_portfolio_risk.py` | Portfolio risk: `PortfolioRiskMonitor`, VaR, concentration, circuit breaker | Rewrite of current 26 |

### 2.3 Practical Layer (15–20)

**Teaching objective**: Complete strategy projects — from signal design to risk management to full backtest.

| No. | File | Teaching Objective | Source |
|-----|------|-------------------|--------|
| 15 | `15_bollinger_strategy.py` | Bollinger mean reversion + stop-loss + A-share applicability analysis | Rewrite of current 14 |
| 16 | `16_macd_volume.py` | MACD trend following + volume confirmation + ATR trailing stop | Rewrite of current 15 |
| 17 | `17_multi_factor.py` | Multi-factor selection: momentum + volume + north-bound sentiment gating | Rewrite of current 16 |
| 18 | `18_grid_trading.py` | Grid trading: price range construction + grid state management | Rewrite of current 17 |
| 19 | `19_sr_portfolio/` | Support/resistance portfolio: multi-target + RSI/MACD/ATR + Donchian confirmation | Rewrite of current 20 |
| 20 | `20_all_weather_alpha/` | All-Weather Alpha: multi-factor selection + sector rotation + technical signals + risk management | Rewrite of current 21 |

### 2.4 Files to Delete

| File | Reason |
|------|--------|
| `06_advanced_api.py` | Content distributed to 07 (scheduling), 09 (attribution), 11 (portfolio) |
| `07_market_data.py` | Content merged into 01 (data APIs) and 13 (A-share data) |
| `13_ptrade_export.py` | Too short (39 lines); content moved to tutorial docs |
| `18_strategy_comparison.py` | Excessive strategy duplication; comparison framework merged into 20 |
| `22_stock_selection_strategy.py` | Functional overlap with 17 |
| `23_small_cap_query_example.py` | `sys.modules` hack is inelegant; `query()` API merged into 04 |
| `24_quick_report_test.py` | Test script, not teaching example; merged into 05 |
| `simple_multi_stock.py` | Prototype quality; superseded by 11 |
| `multi_stock_factor_strategy.py` | Prototype quality; superseded by 17 |

**Total: 31 → 20 files (9 deleted, 2 directories retained as-is with rewrites)**

---

## 3. Shared Infrastructure

### 3.1 Shared Defaults Module

Create `examples/_defaults.py` containing all shared constants:

```python
"""
Shared defaults for all examples.
=================================
Centralizes trading costs, stock selections, and backtest parameters
to ensure consistency across all examples.
"""
from eqlib import OrderCost

# A-share trading costs (2024 current standards)
DEFAULT_ORDER_COST = OrderCost(
    open_tax=0,
    close_tax=0.0005,         # Stamp duty 0.05% (halved since Aug 2023)
    open_commission=0.00025,   # Commission (incl. regulatory fees)
    close_commission=0.00025,
    close_today_commission=0,  # T+1 settlement, no intraday commission
)

# Common backtest targets (selection criteria: high liquidity, representative, complete history)
# Bare codes for data APIs (get_price, attribute_history), suffixed codes for trading APIs (order)
STOCKS = {
    "bank":       "601398",          # ICBC — large-cap blue chip, low volatility
    "insurance":  "601318",          # Ping An — financial conglomerate
    "liquor":     "600519",          # Kweichow Moutai — consumer leader, high price
    "ev":         "002594",          # BYD — new energy, high volatility
    "tech":       "000725",          # BOE — cyclical stock representative
    "pharma":     "600276",          # Hengrui Medicine — healthcare leader
    "cement":     "600585",          # Conch Cement — infrastructure proxy
    "index_hs300": "000300.XSHG",    # CSI 300 benchmark
    "index_sh":    "000001.XSHG",    # Shanghai Composite (reference only)
}
# Suffixed versions for trading APIs: order(), order_target(), etc.
STOCKS_TRADE = {
    "bank":       "601398.XSHG",
    "insurance":  "601318.XSHG",
    "liquor":     "600519.XSHG",
    "ev":         "002594.XSHE",
    "tech":       "000725.XSHE",
    "pharma":     "600276.XSHG",
    "cement":     "600585.XSHG",
}

# Backtest period
BACKTEST_YEARS = 3
INITIAL_CASH = 100_000
```

### 3.2 Data Verification Utility

Each example starts with data availability check:

```python
def verify_data_available(security, start_date, end_date, max_extensions=2):
    """
    Verify data is obtainable with automatic lookback extension.

    If no data in the requested range, extends start_date by 6 months
    per retry (up to max_extensions times). Returns (actual_start, actual_end)
    on success, or exits with clear error message on failure.
    """
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta

    current_start = datetime.strptime(start_date, "%Y-%m-%d")
    for attempt in range(max_extensions + 1):
        try:
            df = get_price(security,
                           current_start.strftime("%Y-%m-%d"),
                           end_date)
            if not df.empty:
                return current_start.strftime("%Y-%m-%d"), end_date
        except Exception as e:
            if attempt == max_extensions:
                print(f"Error: Data fetch failed after {max_extensions+1} attempts: {e}")
                print("  Please check network connection and akshare version")
                sys.exit(1)
        # Extend lookback by 6 months
        current_start -= relativedelta(months=6)
        print(f"  No data found, extending lookback to {current_start.strftime('%Y-%m-%d')}...")

    print(f"Error: {security} has no data even after extending to {current_start.strftime('%Y-%m-%d')}")
    sys.exit(1)
```

### 3.3 Relative Date Strategy

All examples use relative dates instead of hardcoded values:

```python
from datetime import datetime, timedelta

END_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=365 * BACKTEST_YEARS + 30)).strftime("%Y-%m-%d")
```

With fallback: if akshare data is not yet updated, automatically extend lookback.

### 3.4 Unified Evaluation Panel

All practical-layer examples (15–20) end with a standardized evaluation output:

```python
def print_evaluation(result, strategy_name="Strategy"):
    """Standardized evaluation panel — shared by all practical examples."""
    metrics = analyze_returns(result, risk_free_rate=0.03)

    print(f"\n{'='*50}")
    print(f"  {strategy_name} Evaluation Report")
    print(f"{'='*50}")
    print(f"  Annual Return:   {metrics['annual_return']:>8.2%}")
    print(f"  Sharpe Ratio:    {metrics['sharpe_ratio']:>8.2f}")
    print(f"  Max Drawdown:    {metrics['max_drawdown']:>8.2%}")
    print(f"  Win Rate:        {metrics.get('win_rate_trade', 0):>8.1%}")
    print(f"  Profit/Loss:     {metrics.get('profit_loss_ratio', 0):>8.2f}")
    print(f"  Trade Count:     {metrics.get('trade_count', 0):>8.0f}")
    print(f"{'='*50}")

    # Scientific rigor checks
    if metrics.get('trade_count', 0) < 10:
        print("  Warning: Trade count < 10, statistical significance insufficient")
    if abs(metrics['max_drawdown']) > 0.30:
        print("  Warning: Max drawdown > 30%, psychological pressure may be excessive")
```

---

## 4. Code Standards

### 4.1 Docstring Template

Every example file must follow this docstring structure:

```python
"""
{NUMBER} - {TITLE}
{'=' * len(title + number)}

{ONE_PARAGRAPH_DESCRIPTION}

Teaching Objectives:
    - {objective_1}
    - {objective_2}
    - ...

Expected Output:
    - {what the user should see}
    - {metric ranges}

Run:
    python examples/{filename}
"""
```

### 4.2 Import Convention

Use explicit imports instead of `from eqlib import *`:

```python
# GOOD — explicit, readable, IDE-friendly
from eqlib import run_backtest, get_price, attribute_history, order, order_target

# BAD — star import hides dependencies
from eqlib import *
```

### 4.3 Section Structure

Each example follows this internal structure:

```
1. Module docstring (with teaching objectives + expected output)
2. Imports
3. Constants / configuration (using _defaults.py where applicable)
4. Strategy functions (initialize, handle_data, helpers)
5. Main execution block (if __name__ == "__main__")
6. Verification + backtest run + evaluation output
```

### 4.4 Error Handling

Every example must handle common failure modes gracefully:

```python
if __name__ == "__main__":
    print("01 - Data Fetching Example")
    print("=" * 40)

    # Step 1: Verify data availability
    if not verify_data_available(STOCK, START_DATE, END_DATE):
        sys.exit(1)

    # Step 2: Run main logic
    try:
        result = run_backtest(...)
    except Exception as e:
        print(f"Backtest failed: {e}")
        sys.exit(1)

    # Step 3: Output results
    print_evaluation(result, "MA Crossover")
```

### 4.5 No Private API Usage

Examples must only use public APIs. The following are forbidden:

- `from eqlib.engine import _get_preloaded`
- `from eqlib._state import _context`
- `from eqlib.data_cache import _get_local_data_dir`

If a private API is needed for a legitimate use case, file a feature request to expose it publicly first.

---

## 5. Strategy Scientific Rigor

### 5.1 Strategy Design Rationale Block

Each practical-layer example (15–20) must include a "Strategy Design Rationale" block in the docstring:

- **Why this strategy**: Market microstructure justification
- **Why this target**: Stock selection criteria (liquidity, representativeness)
- **Applicable scenarios**: When the strategy works
- **Inapplicable scenarios**: Known limitations
- **References**: Academic or practitioner references where available

### 5.2 Parameter Justification

All strategy parameters must have explicit justification:

- **ATR-based stop-loss** preferred over fixed percentage; if fixed, explain the calculation basis
- **Moving average periods** must reference common practitioner defaults (5/10/20/60)
- **Position sizing** must not exceed 100% total allocation; explain the risk budget
- **Rebalance frequency** must match the strategy's expected holding period

### 5.3 Evaluation Completeness

Every backtest run must output at minimum:

- Annual return (risk-adjusted)
- Sharpe ratio (with stated risk-free rate)
- Maximum drawdown
- Win rate
- Trade count
- At least one risk metric beyond drawdown (Sortino, Calmar, or VaR where applicable)

---

## 6. Tutorial Documentation Fixes

### 6.1 Code Accuracy Fixes

| Issue | Affected Files | Fix |
|-------|---------------|-----|
| Stamp duty `close_tax=0.001` | `how-to/write-strategy.md`, tutorials 01, 04, 05, 08, 10 | Global replace to `0.0005`, add comment "halved since Aug 2023" |
| `fama_french_analysis` deprecated | Tutorial 03, 09, `how-to/run-backtest.md` | Replace with `simple_factor_analysis`, explain deprecation |
| `handle_data(context, bar)` signature | Tutorial 10 A-share sentiment section | Fix to `handle_data(context)`, use `attribute_history` for bar data |
| Commission rate inconsistency | Multiple files `open_commission` ranging 0.0002–0.001 | Unify to `0.00025` (0.025% incl. regulatory fees) |
| Benchmark inconsistency | Some use `000001.XSHG`, some `000300.XSHG` | Unify to `STOCKS["index_hs300"]` with explanation |

### 6.2 Tutorial-to-Example Mapping

| Tutorial | Corresponding Example(s) | Relationship |
|----------|-------------------------|-------------|
| Tutorial 00 Environment Setup | `01_fetch_data.py` | Tutorial guides user to run first example |
| Tutorial 01 First Strategy | `02_write_strategy.py` + `03_run_backtest.py` | Tutorial explains step-by-step, examples are runnable |
| Tutorial 02 Backtest Verification | `03_run_backtest.py` + `05_reports.py` | Report reading maps to report generation example |
| Tutorial 03 Strategy Optimization | `08_utils_library.py` + `09_attribution.py` | Tools and attribution support optimization methods |
| Tutorial 04 Paper to Live | `12_paper_trade.py` | Tutorial explains principles, example demonstrates operation |
| Tutorial 05 RSI Mean Reversion | `15_bollinger_strategy.py` | Tutorial covers RSI theory, example shows Bollinger variant |
| Tutorial 06 Sector Rotation | `10_index_concept.py` | Index/industry data + rotation strategy |
| Tutorial 07 Multi-Factor | `17_multi_factor.py` | Tutorial covers factor theory, example implements selection |
| Tutorial 08 Combined Strategy | `20_all_weather_alpha/` | Tutorial dissects architecture, example provides full implementation |
| Tutorial 09 Param Optimization | `08_utils_library.py` tools section | Expand tutorial with optimization workflow demo |
| Tutorial 10 A-Share Data & Risk | `13_ashare_sentiment.py` + `14_portfolio_risk.py` | Data + risk dual examples |

### 6.3 Code Snippet Synchronization

Use MkDocs `pymdownx.snippets` `--8<--` syntax to reference example source directly.

**Prerequisite**: Add `pymdownx.snippets` to `mkdocs.yml` under `markdown_extensions` (not currently configured):

```yaml
# In mkdocs.yml, add to markdown_extensions:
markdown_extensions:
  # ... existing extensions ...
  - pymdownx.snippets:
      base_path: ["."]  # Allow referencing files from project root
```

**Usage in tutorials**:

```markdown
## Strategy Code

Complete Bollinger strategy implementation (see `examples/15_bollinger_strategy.py`):

```python
--8<-- "examples/15_bollinger_strategy.py:45:78"
```
```

**Benefits**:
- Tutorial code stays in sync with example source automatically
- No manual maintenance of duplicate code
- CI doc builds catch broken references immediately

**Rules**:
- Only reference stable "core snippets" (strategy functions, config constants), not entire files
- Reference ranges use line numbers; update when example files are restructured

### 6.4 Tutorial 09 Expansion

Current: 158 lines (significantly thinner than other tutorials at 449–860 lines).

**Expand to ~400 lines covering**:
- Parameter sensitivity analysis with worked example
- Walk-forward validation concept and implementation
- Multi-period backtest comparison walkthrough
- Diagnostic decision table (from CLAUDE.md) applied to a real case
- Audit logging best practices with complete example

---

## 7. Quality Assurance

### 7.1 Smoke Test Suite

Create `tests/test_examples_smoke.py` with:

- **Syntax check**: `py_compile` on every `.py` file in `examples/`
- **Import check**: Verify all imports resolve (no missing modules)
- **Runtime check**: Core examples (01–07) run actual short-period backtests, verify non-empty results
- **Output validation**: Key metrics in reasonable ranges (e.g., Sharpe between -5 and +10, max drawdown between 0 and -1)

### 7.2 Expected Output Documentation

Each example docstring includes expected output summary with metric ranges, so users know what "correct" looks like.

### 7.3 Review Checklist

Before marking any example as complete:

- [ ] File runs without errors with `python examples/XX_filename.py`
- [ ] All imports are explicit (no star imports)
- [ ] No private API usage
- [ ] Docstring follows template (title, teaching objectives, expected output, run command)
- [ ] Trading costs use `DEFAULT_ORDER_COST` from `_defaults.py`
- [ ] Stock codes use `STOCKS` dict from `_defaults.py` where applicable
- [ ] Dates are relative, not hardcoded
- [ ] Evaluation panel is printed at end
- [ ] Error handling covers data fetch failures
- [ ] Strategy parameters have justification comments
- [ ] Corresponding tutorial code snippets are in sync

---

## 8. Execution Order

### Phase 1: Infrastructure & Bug Fixes
1. Create `examples/_defaults.py`
2. Fix all runtime bugs (2 confirmed)
3. Fix stamp duty across all files
4. Create `tests/test_examples_smoke.py`

### Phase 2: Foundation Layer (01–07)
5. Rewrite 01–07 sequentially
6. Run smoke tests after each

### Phase 3: Intermediate Layer (08–14)
7. Rewrite 08–14 sequentially
8. Run smoke tests after each

### Phase 4: Practical Layer (15–20)
9. Rewrite 15–20 sequentially
10. Run smoke tests after each

### Phase 5: Cleanup
11. Delete 9 deprecated files
12. Update `examples/README.md`
13. Update `docs/examples/index.md`

### Phase 6: Tutorial Sync
14. Fix all code accuracy issues in tutorials
15. Update tutorial-to-example mappings
16. Convert inline code to `--8<--` snippet references where applicable
17. Expand Tutorial 09

### Phase 7: Final Verification
18. Run full test suite
19. Run MkDocs build to verify all doc references
20. Final smoke test on all 20 examples
