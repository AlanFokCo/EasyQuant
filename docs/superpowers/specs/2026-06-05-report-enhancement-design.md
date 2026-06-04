# Report Enhancement Design — Bloomberg Terminal Style

**Date**: 2026-06-05
**Status**: Approved
**Scope**: HTML/PNG/Markdown/JSON backtest report overhaul

---

## 1. Overview

Redesign all four report formats (HTML, PNG, Markdown, JSON) for the EasyQuant backtest engine. Priority use cases:

1. **Personal research & analysis** — high information density, deep data
2. **AI-driven optimization feedback** — structured, machine-readable, zero-inference fields
3. **External presentation** — professional dark-theme visual quality

### Design Philosophy: Bloomberg Terminal

Dark theme, data-dense information walls, monospaced numerics, minimal decoration. Every pixel earns its place.

---

## 2. Color System (Dark Theme)

```
Background layers:
  --bg-primary:      #0c1222     body / deepest background
  --bg-card:         #131b2e     cards / panels
  --bg-elevated:     #1a2438     hover / highlighted elements
  --bg-input:        #0f1729     input fields / table rows

Border layers:
  --border:          #1e2a3a     default borders
  --border-light:    #253042     light separators

Text layers:
  --text-primary:    #e2e8f0     main text
  --text-secondary:  #8b98a9     secondary text
  --text-dim:        #4a5568     annotations / auxiliary

Semantic colors:
  --up:              #26a69a     positive / buy / gain
  --down:            #ef5350     negative / sell / loss
  --accent:          #5b8def     emphasis / links / strategy line
  --warning:         #faad14     warnings / neutral

Chart colors:
  --chart-strategy:  #5b8def     strategy line
  --chart-hs300:     #f0b90b     CSI 300
  --chart-sse:       #e2735a     SSE Composite
  --chart-ma5:       #f0b90b
  --chart-ma20:      #5b8def
  --chart-ma60:      #a855f7
```

### Typography

```css
font-variant-numeric: tabular-nums;
font-feature-settings: "tnum";

/* Number hierarchy */
--num-hero:    42px / 700    grade score
--num-primary: 24px / 600    core metric row
--num-card:    18px / 600    metric cards
--num-table:   13px / 400    table data
```

---

## 3. HTML Report Architecture — 5-Layer Pyramid

```
┌─────────────────────────────────────────────────┐
│  Layer 1: HERO — Grade + Radar + Summary         │
├─────────────────────────────────────────────────┤
│  Layer 2: Core Metrics Row — 4 key numbers       │
├─────────────────────────────────────────────────┤
│  Layer 3: Charts — K-line → Tabbed charts →      │
│           Drawdown → Daily P&L → Daily returns   │
├─────────────────────────────────────────────────┤
│  Layer 4: Analysis Panels (collapsible) —        │
│           Excess returns / Trade quality / Factors│
├─────────────────────────────────────────────────┤
│  Layer 5: Details (collapsible) —                │
│           Trade log / Positions / Data sources    │
└─────────────────────────────────────────────────┘
```

### Layer 1: Hero Section

Three-column layout inside a dark elevated card:

| Column | Content |
|--------|---------|
| Left | Grade letter (S/A/B/C/D) at `--num-hero` size + score out of 100 |
| Center | SVG radar chart (6 axes, inline JS rendering) |
| Right | Auto-generated one-sentence conclusion + key highlights |

**Grade thresholds**: S (>=85) / A (>=70) / B (>=55) / C (>=40) / D (<40)

### Layer 2: Core Metrics Row

4 cards, the single most important number per category:

| Card | Value | Sub-text |
|------|-------|----------|
| Annual Return | +18.3% | comparison vs benchmark |
| Sharpe Ratio | 1.82 | grade badge |
| Max Drawdown | -12.1% | grade badge |
| Win Rate | 63% | + P/L ratio 2.1 |

Each card has a colored grade indicator (excellent/good/fair/poor).

### Layer 3: Charts

**K-line chart** remains full-width, always visible (480px height).

**Tabbed chart area** — same viewport, switchable content:

| Tab | Chart | Technology |
|-----|-------|------------|
| Cumulative Returns | Strategy vs HS300 vs SSE + excess | TradingView Lightweight Charts |
| Monthly Heatmap | GitHub-style contribution grid | CSS Grid |
| Rolling Metrics | 60-day rolling Sharpe / Volatility | TradingView Lightweight Charts |
| Return Distribution | Histogram + statistics | Canvas (inline JS, ~50 lines) |

**Drawdown chart** — enhanced with Top 5 drawdown period annotations (semi-transparent blocks + labels).

**Daily P&L** and **Daily Returns** — kept as-is, dark-themed.

### Layer 4: Analysis Panels (collapsible `<details>`)

Three expandable sections:
- Excess Return Details (daily excess, excess max DD, excess Sharpe, info ratio)
- Trade Quality (win/loss count, profit/loss ratio, per-stock P&L breakdown)
- Factor Attribution (Brinson + Fama-French)

### Layer 5: Detail Panels (collapsible `<details>`)

Three expandable sections:
- Trade Log (full table with date, action, security, price, amount, commission)
- Current Positions
- Data Sources & Methodology

### Existing Elements Preserved

- RSI and MACD sub-charts (dark-themed)
- Trade calendar
- Indicator toggle panel (MA/BB/VOL/SR)
- Symbol selector dropdown
- Crosshair legend
- Mobile/tablet responsive breakpoints (updated for dark theme)

---

## 4. Strategy Grading System

### Six Dimensions

| Dimension | Metrics | Weight | Score Interpolation (0-100) |
|-----------|---------|--------|-----------------------------|
| Return Capability | annual_return, alpha | 20% | Linear: <=0%=0, 8%=60, 15%=85, >=25%=100. Alpha bonus: +5 per 1% alpha (capped +15) |
| Risk Control | max_drawdown, volatility | 20% | DD component: <10%=100, <20%=75, <30%=50, >=30%=25. Vol component: <12%=100, <20%=75, <30%=50, >=30%=25. Average of both |
| Risk Adjusted | sharpe, sortino, calmar | 20% | Sharpe-driven: <=0=0, 0.5=50, 1.0=75, 1.5=90, >=2.0=100. Sortino/Calmar as tiebreakers (+/- 5) |
| Trade Quality | win_rate, pl_ratio, trade_count | 15% | 50% from win_rate (50%=75, 60%=90, 70%=100), 30% from PL ratio (1.5=50, 2.0=75, 3.0=100), 20% from trade_count sufficiency (>=10=100, >=5=75, <5=50) |
| Excess Capability | excess_return, info_ratio | 15% | Linear: excess<=0=0, bench*0.5=50, bench*1.0=75, bench*1.5=90, bench*2.0=100. IR bonus: +5 per 0.5 IR (capped +10) |
| Stability | monthly_win_rate, rolling_sharpe_std | 10% | Monthly WR: 50%=50, 60%=70, 70%=85, 80%=100. Penalize rolling_sharpe_std > 0.5 by -10 |

**Overall score**: weighted sum of dimension scores (0-100)

**Grade thresholds**: S (>=85) / A (>=70) / B (>=55) / C (>=40) / D (<40)

### Summary Text Generation

Template-based, driven by grade + key metrics:
- S-grade: "Strategy performs excellently: annual +18.3% with max drawdown only -12.1%, Sharpe 1.82 demonstrates outstanding risk-adjusted returns"
- C-grade: "Strategy underperforms: annual +3.2% failed to beat CSI 300 (+8.1%), max drawdown -28.7% exceeds tolerance"

---

## 5. New Charts

### 5.1 Monthly Returns Heatmap

**Data**: `monthly_returns` dict from `analyze_returns()`
```python
monthly_returns: {"2024-01": 0.0321, "2024-02": -0.0153, ...}
```

**Rendering**: CSS Grid, each cell colored by return magnitude:
```
> +5%   → deep green   rgba(38,166,154, 0.9)
+2~5%   → mid green    rgba(38,166,154, 0.5)
0~2%    → light green  rgba(38,166,154, 0.2)
0       → grey         rgba(139,152,169, 0.1)
-2~0%   → light red    rgba(239,83,80, 0.2)
<-2%    → deep red     rgba(239,83,80, 0.5)
```

**Footer stats row**: annual return, monthly mean, monthly win rate, best month, worst month.

### 5.2 Rolling Metrics Curves

**Data**: `rolling_sharpe_60d`, `rolling_volatility_60d` from `analyze_returns()`
```python
rolling_sharpe: [{"time": "2024-02-20", "value": 1.32}, ...]
rolling_volatility: [{"time": "2024-02-20", "value": 0.158}, ...]
```

**Rendering**: Two Lightweight Charts sub-panels with reference lines (Sharpe=1.0, Vol=20%).

**Interaction**: Tab switch between Sharpe / Volatility / Drawdown views.

### 5.3 Return Distribution Histogram

**Data**: `daily_returns_stats` from `analyze_returns()`
```python
{
    "mean": 0.00082, "std": 0.0123,
    "skewness": -0.35, "kurtosis": 3.82,
    "best_day": 0.0321, "worst_day": -0.0287,
    "positive_days": 142, "negative_days": 110,
    "histogram": [{"bin": -0.03, "count": 2}, ...]
}
```

**Rendering**: Canvas histogram (~50 lines inline JS), no external library.

### 5.4 Strategy Radar Chart (SVG)

**Data**: `grade.dimensions` (six scores, 0-100 each)

**Rendering**: Inline SVG generated by JS — hexagonal grid + filled polygon + axis labels.

### 5.5 Drawdown Period Annotations

**Data**: `drawdown_periods` from `analyze_returns()`
```python
[
    {"rank": 1, "start": "2024-03-15", "trough": "2024-04-02",
     "recovery": "2024-05-10", "depth": -0.121, "duration_days": 56, "recovery_days": 38}
]
```

**Rendering**: Semi-transparent colored blocks on existing drawdown curve, with rank labels.

---

## 6. PNG Chart Upgrade

Single image, upgraded from current 2-panel to 4-panel compact layout:

```
┌─────────────────────────────────────────────────┐
│ [Brand Logo]  Backtest Report · 000001           │
│ Grade: S / 87  |  PnL: +18,300 (+18.3%)         │
├─────────────────────────────────────────────────┤
│ Strategy vs Benchmark cumulative return (%)      │
│ + Radar chart thumbnail (top-right corner)       │
├─────────────────────────────────────────────────┤
│ Drawdown (%)                                     │
│ Monthly returns strip: Jan +3.2% Feb -1.5% ...   │
└─────────────────────────────────────────────────┘
```

**Color scheme**: matches HTML dark theme (`#0c1222` background, same chart colors).

**matplotlib**: `apply_matplotlib_brand()` updated for dark theme compatibility.

---

## 7. Markdown Report Enhancement

### New Structure

```markdown
# Backtest Report — {symbol}
*Generated by EasyQuant · {dates} · Grade: {grade} ({score}/100)*

## Strategy Summary
> One-sentence conclusion with key metrics and actionable insight.

## Grade Breakdown
| Dimension | Score | Grade | Key Metric |
(table with 6 dimensions + overall)

## Performance Metrics
| Metric | Value | Benchmark | Delta |
(core metrics with benchmark comparison)

## Monthly Returns
| Month | Jan | Feb | ... | Dec | YTD |
(heatmap-as-table)

## Rolling Metrics (60-day window, quarterly sampled)
| Date | Rolling Sharpe | Rolling Vol | Rolling MaxDD |

## Top 5 Drawdown Periods
| # | Start | Trough | Recovery | Depth | Duration |

## Trade Analysis
(existing trade P&L table + per-stock summary)

## Excess Return Analysis
(existing)

## Factor Analysis
(existing Brinson + Fama-French)

## Data Sources & Methodology
(existing)
```

### Key Changes

1. **Top-level summary** — AI reads qualitative judgment immediately
2. **Grade breakdown table** — AI quickly identifies weakest dimension
3. **Monthly returns table** — time-dimension analysis
4. **Rolling metrics table** — stability analysis (quarterly sample, 4 rows)
5. **Top 5 drawdown table** — risk event localization

---

## 8. JSON Report — Agent-First Design

### Design Principles

- AI Agent should know what to do after reading the first field
- Zero inference required — thresholds, pass/fail, and actions are pre-computed
- Iteration tracking built-in for multi-round optimization

### Structure (8 Layers)

#### Layer 1: `verdict` — Decision Entry Point

```json
{
  "pass": false,
  "grade": "B",
  "score": 78,
  "bottleneck": "risk_control",
  "action": "adjust_params",
  "summary": "Annual +12.5% beats benchmark, but drawdown -19.8% near 20% limit. Prioritize tightening stop-loss or reducing position size."
}
```

Agent reads `verdict.pass` → if true, optimization complete. If false, reads `verdict.action` to decide next step.

#### Layer 2: `targets` — Optimization Targets

```json
[
  {
    "metric": "sharpe_ratio",
    "value": 1.32,
    "target": {"op": ">=", "threshold": 1.0},
    "pass": true,
    "gap": "+0.32",
    "priority": null
  },
  {
    "metric": "max_drawdown",
    "value": -0.198,
    "target": {"op": ">=", "threshold": -0.20},
    "pass": false,
    "gap": "-0.002",
    "priority": 1
  }
]
```

Agent iterates `targets[]`, finds `pass=false` items sorted by `priority`.

#### Layer 3: `diagnostics` — Root Cause Analysis

```json
[
  {
    "metric": "max_drawdown",
    "severity": "critical",
    "finding": "Max drawdown -19.8% only 0.2% from 20% tolerance",
    "root_cause": "No position reduction during Mar-Apr decline, single worst trade lost 8.3% of portfolio",
    "affected_period": "2024-03-15 to 2024-04-02",
    "related_metrics": {
      "worst_single_trade_pnl": -8300.0,
      "worst_single_trade_pct": -0.083,
      "consecutive_loss_days": 12,
      "max_loss_in_drawdown": -0.121
    }
  }
]
```

#### Layer 4: `recommendations` — Parameter Suggestions

```json
[
  {
    "priority": 1,
    "target_metric": "max_drawdown",
    "action": "decrease",
    "parameter": "stop_loss_pct",
    "current": 0.08,
    "suggested": 0.06,
    "range": [0.02, 0.30],
    "rationale": "Current 8% stop-loss, tighten to 6% to cut losses earlier",
    "expected_effect": "max_drawdown estimated improvement 3-5%",
    "risk": "May increase stop-loss trigger frequency, reduce win rate 2-3%"
  }
]
```

Agent reads `recommendations[0]`, applies Edit to `PARAMS[parameter]` = `suggested`.

#### Layer 5: `strategy_params` — Current Parameter State

```json
{
  "current": {"fast_period": 5, "slow_period": 20, "stop_loss_pct": 0.08},
  "constraints": ["fast_period < slow_period", "stop_loss_pct in (0, 0.30)"]
}
```

Agent validates against constraints before applying changes.

#### Layer 6: `iteration` — Iteration Tracking

```json
{
  "run_id": "run_abc123",
  "previous_run_id": "run_xyz789",
  "changes_applied": {"fast_period": {"from": 5, "to": 8}},
  "score_delta": +5,
  "previous_grade": "C",
  "metric_deltas": {
    "annual_return": {"from": 0.098, "to": 0.125, "delta": "+0.027", "improved": true},
    "max_drawdown": {"from": -0.253, "to": -0.198, "delta": "+0.055", "improved": true}
  },
  "regression_detected": false,
  "convergence_note": "3 consecutive rounds of max_drawdown improvement, still not at target"
}
```

Agent reads `regression_detected` to decide whether to revert.

#### Layer 7: `grade` — Six-Dimension Scoring

```json
{
  "overall": "B",
  "score": 78,
  "dimensions": [
    {"name": "return_capability", "score": 72, "grade": "B", "key": {"annual_return": 0.125, "alpha": 0.038}},
    {"name": "risk_control", "score": 65, "grade": "C", "key": {"max_drawdown": -0.198, "volatility": 0.163}}
  ],
  "weakest": "risk_control",
  "strongest": "excess_capability"
}
```

#### Layer 8: `metrics` / `time_series` / `daily_returns_stats` / `per_stock_pnl` — Raw Data

Evidence layer — all raw numbers, monthly returns, rolling series, drawdown periods, per-stock P&L. Preserves backward compatibility with existing JSON consumers.

### Agent Reading Flow

```
1. Read verdict.pass → true? → optimization complete
                            → false → read verdict.action
2. action == "adjust_params"?
   → read targets[] find pass=false with highest priority
   → read recommendations[] for parameter suggestion
   → read strategy_params.constraints to validate
   → Edit PARAMS
3. After next iteration → read iteration.metric_deltas to confirm direction
4. If regression_detected → revert previous parameter change
```

---

## 9. Data Pipeline — Backend Additions

All computation lives in `eqlib/attribution.py` (data layer). `report.py` only formats and renders.

### `analyze_returns()` New Return Fields

All rolling windows use **trading days** (not calendar days). 60 trading days ≈ 3 calendar months.

```python
# Existing fields — unchanged (backward compatible)
"sharpe_ratio", "sortino_ratio", "max_drawdown", "annual_return", ...

# New fields added:
"monthly_returns": {"2024-01": 0.0321, ...},           # month-end return
"rolling_sharpe_60d": [{"date": "...", "value": 1.32}, ...],    # 60 trading-day window
"rolling_volatility_60d": [{"date": "...", "value": 0.158}, ...], # 60 trading-day window
"daily_returns_raw": [0.012, -0.008, ...],             # raw daily return array
"per_stock_pnl": {"000001.XSHE": 3250.50, ...},        # per-security aggregated P&L
"drawdown_periods": [                                    # top 5 drawdown events
    {"start": "...", "trough": "...", "recovery": "...",
     "depth": -0.121, "duration_days": 56, "recovery_days": 38}
],
"daily_returns_stats": {
    "mean": 0.00082, "std": 0.0123,
    "skewness": -0.35, "kurtosis": 3.82,
    "best_day": 0.0321, "worst_day": -0.0287,
    "positive_days": 142, "negative_days": 110,
    "histogram": [{"bin": -0.03, "count": 2}, ...]
},
"grade": grade_strategy(analytics)   # computed inline, see Section 4
```

### New Functions in `attribution.py`

```python
def grade_strategy(analytics) -> dict:
    """Compute 6-dimension scores, overall grade, and summary text.
    Returns: {overall, score, dimensions, weakest, strongest, summary_text}
    """

def diagnose_bottleneck(analytics, grade) -> list:
    """Identify failing metrics and root causes.
    Returns: [{metric, severity, finding, root_cause, affected_period, related_metrics}]
    """

def recommend_params(analytics, grade, current_params=None, param_ranges=None) -> list:
    """Suggest parameter adjustments based on diagnostics.

    current_params and param_ranges are optional — they come from the strategy
    file (PARAMS and PARAM_RANGES dicts), NOT from the backtest result dict.
    If not provided, recommendations use rule-based defaults without specific
    parameter names or ranges.

    Returns: [{priority, target_metric, action, parameter, current, suggested,
               range, rationale, expected_effect, risk}]
    """
```

### Data Flow Boundaries

Not all JSON fields are produced by the report generator alone. Some require input from the orchestrator:

| JSON Layer | Produced By | Data Source |
|------------|-------------|-------------|
| `verdict` | `generate_report_json()` | `analyze_returns()` + `grade_strategy()` |
| `targets` | `generate_report_json()` | `analyze_returns()` + CLAUDE.md thresholds |
| `diagnostics` | `generate_report_json()` | `diagnose_bottleneck()` |
| `recommendations` | `generate_report_json()` | `recommend_params()` — needs `current_params` and `param_ranges` from strategy file |
| `strategy_params` | **Orchestrator** | Claude Code reads strategy file's `PARAMS` and `PARAM_RANGES` |
| `iteration` | **Orchestrator** | Claude Code provides `previous_run_id`, `changes_applied`, reads previous JSON report for `metric_deltas` |
| `grade` | `generate_report_json()` | `grade_strategy()` |
| `metrics` / `time_series` | `generate_report_json()` | `analyze_returns()` |

**`generate_report_json()` signature update**:

```python
def generate_report_json(result, out_path, *,
                         strategy_params=None,      # from orchestrator
                         iteration_context=None):    # from orchestrator
    """
    strategy_params: {"current": {...}, "constraints": [...]} or None
    iteration_context: {"run_id": "...", "previous_run_id": "...",
                        "changes_applied": {...}, "previous_metrics": {...}} or None
    """
```

When `strategy_params` is None, the `strategy_params` JSON layer is omitted.
When `iteration_context` is None, the `iteration` JSON layer is omitted.
This keeps the function callable from simple scripts while enabling full agent features.

### Backward Compatibility Guarantee

```python
# Existing usage — unchanged
metrics = analyze_returns(result)
sharpe = metrics['sharpe_ratio']  # still works

# New fields naturally available
monthly = metrics['monthly_returns']      # new
grade   = metrics['grade']               # new
rolling = metrics['rolling_sharpe_60d']   # new
```

---

## 10. File Change Scope

```
eqlib/
  attribution.py     MODIFY — analyze_returns() new return fields
                     ADD — grade_strategy()
                     ADD — diagnose_bottleneck()
                     ADD — recommend_params()
  report.py          REWRITE — _HTML_TEMPLATE (dark theme)
                     REWRITE — generate_chart() (PNG 4-panel)
                     REWRITE — generate_report_md() (enhanced structure)
                     REWRITE — generate_report_json() (Agent-First)
                     MODIFY — _calc_metrics() pass new data
                     ADD — _calc_strategy_score()
                     ADD — _build_summary_text()
  brand.py           MODIFY — dark theme color palette extension
```

No new files. No new pip/npm dependencies.

---

## 11. Constraints

| Constraint | Handling |
|------------|---------|
| `analyze_returns()` is public API | Only add new return fields, never remove/change existing ones |
| `_HTML_TEMPLATE` currently ~1600 lines | Full rewrite to dark theme, inline JS/CSS pattern preserved |
| No new dependencies | Radar = inline SVG/JS, Histogram = Canvas, Heatmap = CSS Grid |
| CLAUDE.md "don't modify eqlib/" rule | That rule applies during strategy optimization; this is core library enhancement |
| Existing 449 tests pass | `analyze_returns()` new fields don't affect existing tests; new functions need new tests |

---

## 12. Testing Strategy

### New Tests

| Test File | Content |
|-----------|---------|
| `tests/test_attribution.py` | `grade_strategy()` scoring logic, dimension scores, grade thresholds, interpolation edge cases |
| `tests/test_report.py` | All 4 formats generate successfully, new fields present, HTML contains dark theme tokens |

### Regression Gate — All Must Pass Before Merge

| Command | Purpose |
|---------|---------|
| `python -m pytest tests/ -v` | Full test suite (currently 449 tests) — zero failures allowed |
| `python -m pytest tests/test_examples_smoke.py -v` | All example smoke tests — every example must still run |
| `python examples/03_run_backtest.py` | Manual smoke: backtest generates all 4 report formats without error |
| `python -c "from eqlib import *; print('eqlib OK')"` | Import sanity check |
| `mkdocs build --strict` | Doc build (if any doc changes) |

### Backward Compatibility Verification

Existing code that calls `analyze_returns()` must continue to work unchanged:
```python
metrics = analyze_returns(result)
assert 'sharpe_ratio' in metrics      # existing field still present
assert 'max_drawdown' in metrics      # existing field still present
assert isinstance(metrics['grade'], dict)  # new field available
```

All existing examples and tutorial scripts that generate reports must produce valid output with the new code.

---

## 13. Visual Reference: HTML Layout

### Before (current)

```
┌─── White Header ──────────────────────────────┐
│  Logo + Report Title + PnL Badge               │
├───────────────────────────────────────────────┤
│ [Init] [Final] [PnL] [Ret%] [Buy] [Sell]      │  6 summary cards
│ [AnnRet] [Excess] [HS300] [Alpha] [Beta]       │  11 metrics flat
│       [Sharpe] [WinRate] [PLRatio] [MaxDD] ... │
│ [DailyExcess] [ExcessDD] [ExcessSharpe] ...    │  10 secondary flat
├───────────────────────────────────────────────┤
│ K-line (480px) → RSI → MACD → Returns →       │  all expanded
│ Drawdown → Daily PnL → Daily Ret → Trades     │
└───────────────────────────────────────────────┘
```

### After (new)

```
┌─── Dark Header ───────────────────────────────────────────┐
│  Logo  │ Report · 000001  2024.01-12.31  │  S Grade / 87  │
├───────────────────────────────────────────────────────────┤
│  HERO: [S/87] [Radar SVG] [Summary text]                  │
├───────────────────────────────────────────────────────────┤
│  CORE: [AnnRet +18.3%] [Sharpe 1.82] [MaxDD -12.1%] [WR 63%]│
├───────────────────────────────────────────────────────────┤
│  K-line (always visible, 480px)                           │
├───────────────────────────────────────────────────────────┤
│  TABS: [Cumulative] [Heatmap] [Rolling] [Distribution]    │
│  (same viewport, switchable)                              │
├───────────────────────────────────────────────────────────┤
│  Drawdown (enhanced with Top 5 annotations)               │
│  Daily PnL │ Daily Returns                                │
├───────────────────────────────────────────────────────────┤
│  ▸ Analysis: Excess Returns │ Trade Quality │ Factors     │
├───────────────────────────────────────────────────────────┤
│  ▸ Details: Trade Log │ Positions │ Data Sources          │
└───────────────────────────────────────────────────────────┘
```
