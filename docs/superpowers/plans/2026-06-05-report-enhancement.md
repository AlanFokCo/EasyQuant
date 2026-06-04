# Report Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all four backtest report formats (HTML, PNG, Markdown, JSON) with Bloomberg Terminal dark theme, strategy grading system, and Agent-First JSON structure.

**Architecture:** Data pipeline enhancements in `attribution.py` (new fields + 3 new functions) feed all four report generators in `report.py`. HTML template rewritten with dark CSS, 5-layer pyramid layout, tabbed charts, radar SVG, monthly heatmap, rolling metrics, and return distribution. JSON report restructured as Agent-First with verdict/targets/diagnostics/recommendations layers. PNG upgraded to 4-panel dark layout. Markdown restructured with grade breakdown and monthly tables.

**Tech Stack:** Python (numpy, pandas, scipy.stats for skew/kurtosis, matplotlib), HTML/CSS/JS (TradingView Lightweight Charts 4.1.1, inline SVG, Canvas, CSS Grid). No new pip/npm dependencies added.

**Spec:** `docs/superpowers/specs/2026-06-05-report-enhancement-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `eqlib/brand.py` | MODIFY | Add `DARK_COLORS` dict and matplotlib dark theme helper |
| `eqlib/attribution.py` | MODIFY | Add fields to `analyze_returns()`, add `grade_strategy()`, `diagnose_bottleneck()`, `recommend_params()` |
| `eqlib/__init__.py` | MODIFY | Export new public functions |
| `eqlib/report.py` | REWRITE | All 4 generators + `_calc_metrics()` + HTML template + `_calc_strategy_score()` + `_build_summary_text()` |
| `tests/test_attribution_grading.py` | CREATE | Tests for grading, diagnosis, recommendation functions |
| `tests/test_report_formats.py` | CREATE | Tests for all 4 report format generators with new fields |

---

### Task 1: Dark Theme Color Palette in brand.py

**Files:**
- Modify: `eqlib/brand.py` (add after existing content, ~30 lines)
- Test: existing tests unaffected

- [ ] **Step 1: Add dark color constants to brand.py**

Append the following to the end of `eqlib/brand.py`:

```python
# ============================================================
# Dark theme color palette for reports (Bloomberg Terminal style)
# ============================================================

DARK_COLORS = {
    # Background layers
    "bg_primary": "#0c1222",
    "bg_card": "#131b2e",
    "bg_elevated": "#1a2438",
    "bg_input": "#0f1729",
    # Borders
    "border": "#1e2a3a",
    "border_light": "#253042",
    # Text
    "text_primary": "#e2e8f0",
    "text_secondary": "#8b98a9",
    "text_dim": "#4a5568",
    # Semantic
    "up": "#26a69a",
    "down": "#ef5350",
    "accent": "#5b8def",
    "warning": "#faad14",
    # Chart
    "chart_strategy": "#5b8def",
    "chart_hs300": "#f0b90b",
    "chart_sse": "#e2735a",
    "chart_ma5": "#f0b90b",
    "chart_ma20": "#5b8def",
    "chart_ma60": "#a855f7",
}


def apply_matplotlib_dark_theme(fig):
    """Apply dark theme styling to a matplotlib Figure for PNG report."""
    c = DARK_COLORS
    fig.patch.set_facecolor(c["bg_primary"])
    for ax in fig.axes:
        ax.set_facecolor(c["bg_card"])
        ax.tick_params(colors=c["text_secondary"], labelsize=8)
        ax.xaxis.label.set_color(c["text_secondary"])
        ax.yaxis.label.set_color(c["text_secondary"])
        ax.title.set_color(c["text_primary"])
        for spine in ax.spines.values():
            spine.set_color(c["border"])
        ax.grid(True, alpha=0.15, color=c["border_light"])
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from eqlib.brand import DARK_COLORS, apply_matplotlib_dark_theme; print(len(DARK_COLORS), 'colors'); print('OK')"`
Expected: `20 colors` then `OK`

- [ ] **Step 3: Commit**

```bash
git add eqlib/brand.py
git commit -m "feat: add dark theme color palette and matplotlib helper to brand.py"
```

---

### Task 2: Extend analyze_returns() with New Fields

**Files:**
- Modify: `eqlib/attribution.py:130-213` (add computations before the `return` dict, then add new keys to return dict)
- Test: existing `analyze_returns()` callers unaffected (new fields are additive)

- [ ] **Step 1: Add new computations before the return statement**

In `analyze_returns()`, after the line `daily_excess_ret = 0.0` (around line 178) and before `return {` (line 181), insert the following block. The variables `values`, `daily_ret`, `trades`, `ann_factor`, `risk_free_rate`, and `daily_rf` are already defined above this point:

```python
    # ── Monthly returns ─────────────────────────────────────────────
    monthly_returns = {}
    monthly_vals = values.resample("ME").last()
    prev_val = initial
    for dt, val in monthly_vals.items():
        if pd.notna(val) and prev_val > 0:
            monthly_returns[dt.strftime("%Y-%m")] = round(float(val / prev_val - 1), 6)
            prev_val = val

    # ── Rolling metrics (60 trading-day window) ─────────────────────
    window = min(60, n_days)
    rolling_mean = daily_ret.rolling(window).mean()
    rolling_std = daily_ret.rolling(window).std()
    rolling_sharpe_60d = []
    rolling_volatility_60d = []
    if window >= 10 and not rolling_std.dropna().empty:
        for dt in rolling_mean.dropna().index:
            rm = rolling_mean.loc[dt]
            rs = rolling_std.loc[dt]
            if rs > 0 and np.isfinite(rm) and np.isfinite(rs):
                s = float((rm - daily_rf) / rs * np.sqrt(ann_factor))
                v = float(rs * np.sqrt(ann_factor))
                rolling_sharpe_60d.append({"date": dt.strftime("%Y-%m-%d"), "value": round(s, 3)})
                rolling_volatility_60d.append({"date": dt.strftime("%Y-%m-%d"), "value": round(v, 4)})

    # ── Daily returns statistics ─────────────────────────────────────
    from scipy.stats import skew, kurtosis
    dr_array = daily_ret.values
    daily_returns_stats = {
        "mean": float(daily_ret.mean()),
        "std": float(daily_ret.std()),
        "skewness": float(skew(dr_array)) if len(dr_array) > 3 else 0.0,
        "kurtosis": float(kurtosis(dr_array)) if len(dr_array) > 3 else 0.0,
        "best_day": float(daily_ret.max()),
        "worst_day": float(daily_ret.min()),
        "positive_days": int((daily_ret > 0).sum()),
        "negative_days": int((daily_ret < 0).sum()),
        "histogram": [
            {"bin": round(b, 4), "count": int(((daily_ret >= b) & (daily_ret < b + 0.005)).sum())}
            for b in np.arange(-0.05, 0.05, 0.005)
        ],
    }

    # ── Per-stock P&L ───────────────────────────────────────────────
    from collections import deque as _deque
    _buy_q = {}
    per_stock_pnl = {}
    for trade in trades:
        sec = trade["security"]
        t_type = trade.get("type")
        if t_type not in ("BUY", "SELL"):
            continue
        price = trade["price"]
        amount = trade["amount"]
        if t_type == "BUY":
            _buy_q.setdefault(sec, _deque()).append((price, amount))
        elif t_type == "SELL":
            remaining = amount
            q = _buy_q.get(sec, _deque())
            total_cost = 0.0
            total_matched = 0
            while remaining > 0 and q:
                bp, ba = q[0]
                matched = min(ba, remaining)
                total_cost += bp * matched
                total_matched += matched
                remaining -= matched
                if matched == ba:
                    q.popleft()
                else:
                    q[0] = (bp, ba - matched)
            if total_matched > 0:
                avg_buy = total_cost / total_matched
                pnl = (price - avg_buy) * total_matched
                per_stock_pnl[sec] = per_stock_pnl.get(sec, 0.0) + pnl

    # ── Top 5 drawdown periods ──────────────────────────────────────
    _peak = values.cummax()
    _dd = (values - _peak) / _peak
    drawdown_periods = []
    in_dd = False
    dd_start = dd_trough = None
    dd_depth = 0.0
    for dt, dd_val in _dd.items():
        if dd_val < 0:
            if not in_dd:
                in_dd = True
                dd_start = dt
                dd_trough = dt
                dd_depth = dd_val
            elif dd_val < dd_depth:
                dd_trough = dt
                dd_depth = dd_val
        else:
            if in_dd and dd_start is not None:
                drawdown_periods.append({
                    "start": dd_start.strftime("%Y-%m-%d"),
                    "trough": dd_trough.strftime("%Y-%m-%d"),
                    "recovery": dt.strftime("%Y-%m-%d"),
                    "depth": round(float(dd_depth), 4),
                    "duration_days": (dt - dd_start).days,
                    "recovery_days": (dt - dd_trough).days,
                })
                in_dd = False
    if in_dd and dd_start is not None:
        last_dt = values.index[-1]
        drawdown_periods.append({
            "start": dd_start.strftime("%Y-%m-%d"),
            "trough": dd_trough.strftime("%Y-%m-%d"),
            "recovery": None,
            "depth": round(float(dd_depth), 4),
            "duration_days": (last_dt - dd_start).days,
            "recovery_days": None,
        })
    drawdown_periods.sort(key=lambda x: x["depth"])
    for i, dp in enumerate(drawdown_periods[:5]):
        dp["rank"] = i + 1
    drawdown_periods = drawdown_periods[:5]
```

- [ ] **Step 2: Add new fields to the return dict**

In the `return { ... }` dict (line 181), add these new keys at the end (before the closing `}`):

```python
        # New fields for enhanced reports
        "monthly_returns": monthly_returns,
        "rolling_sharpe_60d": rolling_sharpe_60d,
        "rolling_volatility_60d": rolling_volatility_60d,
        "daily_returns_stats": daily_returns_stats,
        "per_stock_pnl": per_stock_pnl,
        "drawdown_periods": drawdown_periods,
```

- [ ] **Step 3: Run existing tests to verify backward compatibility**

Run: `python -m pytest tests/ -v --tb=short -x`
Expected: All existing tests pass (449+). New fields are purely additive.

- [ ] **Step 4: Quick smoke test of new fields**

Run:
```bash
python -c "
from eqlib import *
from examples._defaults import *
import examples._defaults as d

result = run_backtest(
    initialize_func=lambda ctx: None,
    start_date='2024-01-01', end_date='2024-03-31',
    starting_cash=100000, benchmark='000300.XSHG',
    securities=['601318'], use_local=True,
)
if result:
    m = analyze_returns(result)
    for k in ['monthly_returns','rolling_sharpe_60d','rolling_volatility_60d',
              'daily_returns_stats','per_stock_pnl','drawdown_periods']:
        print(f'{k}: {type(m.get(k)).__name__} = {str(m.get(k))[:80]}')
    print('OK')
else:
    print('SKIP (no data)')
"
```
Expected: All 6 new fields present with correct types. `OK` printed.

- [ ] **Step 5: Commit**

```bash
git add eqlib/attribution.py
git commit -m "feat: add monthly returns, rolling metrics, daily stats, per-stock PnL, drawdown periods to analyze_returns()"
```

---

### Task 3: Add grade_strategy(), diagnose_bottleneck(), recommend_params()

**Files:**
- Modify: `eqlib/attribution.py` (append after existing functions, ~200 lines)
- Test: `tests/test_attribution_grading.py` (created in Task 6)

- [ ] **Step 1: Add grade_strategy() at end of attribution.py**

Append to `eqlib/attribution.py`:

```python
def grade_strategy(analytics) -> dict:
    """Compute 6-dimension scores, overall grade, and summary text.

    See spec: docs/superpowers/specs/2026-06-05-report-enhancement-design.md §4

    Returns:
        dict with keys: overall (str), score (float), dimensions (list of dicts),
        weakest (str), strongest (str), summary_text (str).
    """
    if analytics is None:
        return {"overall": "D", "score": 0, "dimensions": [],
                "weakest": "", "strongest": "", "summary_text": "Insufficient data."}

    dims = []

    # --- Return Capability (weight 0.20) ---
    ann_ret = analytics.get("annual_return", 0)
    alpha = analytics.get("alpha", 0)
    ret_score = max(0, min(100, ann_ret / 0.25 * 100))
    alpha_bonus = max(0, min(15, alpha / 0.01 * 5))
    ret_score = min(100, ret_score + alpha_bonus)
    dims.append({"name": "return_capability", "score": round(ret_score, 1),
                 "key": {"annual_return": ann_ret, "alpha": alpha}})

    # --- Risk Control (weight 0.20) ---
    max_dd = abs(analytics.get("max_drawdown", 0))
    vol = analytics.get("annual_volatility", 0)
    dd_score = 100 if max_dd < 0.10 else 75 if max_dd < 0.20 else 50 if max_dd < 0.30 else 25
    vol_score = 100 if vol < 0.12 else 75 if vol < 0.20 else 50 if vol < 0.30 else 25
    risk_score = (dd_score + vol_score) / 2
    dims.append({"name": "risk_control", "score": round(risk_score, 1),
                 "key": {"max_drawdown": analytics.get("max_drawdown", 0),
                         "volatility": vol}})

    # --- Risk Adjusted (weight 0.20) ---
    sharpe = analytics.get("sharpe_ratio", 0)
    sortino = analytics.get("sortino_ratio", 0)
    calmar = analytics.get("calmar_ratio", 0)
    adj_score = max(0, min(100, sharpe / 2.0 * 100))
    if sortino > 2.0:
        adj_score = min(100, adj_score + 5)
    if calmar > 1.5:
        adj_score = min(100, adj_score + 5)
    dims.append({"name": "risk_adjusted", "score": round(adj_score, 1),
                 "key": {"sharpe": sharpe, "sortino": sortino, "calmar": calmar}})

    # --- Trade Quality (weight 0.15) ---
    win_rate = analytics.get("win_rate_trade", 0)
    pl_ratio = analytics.get("profit_loss_ratio", 0)
    if pl_ratio == float("inf"):
        pl_ratio = 10.0
    trade_count = analytics.get("trade_count", 0)
    wr_score = max(0, min(100, win_rate / 0.70 * 100))
    pl_score = max(0, min(100, pl_ratio / 3.0 * 100))
    tc_score = 100 if trade_count >= 10 else 75 if trade_count >= 5 else 50
    trade_score = wr_score * 0.5 + pl_score * 0.3 + tc_score * 0.2
    dims.append({"name": "trade_quality", "score": round(trade_score, 1),
                 "key": {"win_rate": win_rate, "pl_ratio": pl_ratio,
                         "trade_count": trade_count}})

    # --- Excess Capability (weight 0.15) ---
    excess_ret = analytics.get("excess_return", 0)
    info_ratio = analytics.get("information_ratio", 0)
    bench_ret = analytics.get("benchmark_return", 0)
    bench_ref = abs(bench_ret) if abs(bench_ret) > 0.01 else 0.05
    excess_score = max(0, min(100, excess_ret / (bench_ref * 2.0) * 100))
    ir_bonus = max(0, min(10, info_ratio / 0.5 * 5))
    excess_score = min(100, excess_score + ir_bonus)
    dims.append({"name": "excess_capability", "score": round(excess_score, 1),
                 "key": {"excess_return": excess_ret, "info_ratio": info_ratio}})

    # --- Stability (weight 0.10) ---
    monthly_wr = 0.0
    mr = analytics.get("monthly_returns", {})
    if mr:
        positive_months = sum(1 for v in mr.values() if v > 0)
        monthly_wr = positive_months / len(mr)
    stab_score = max(0, min(100, monthly_wr / 0.80 * 100))
    dims.append({"name": "stability", "score": round(stab_score, 1),
                 "key": {"monthly_win_rate": round(monthly_wr, 3)}})

    # Overall weighted score
    weights = [0.20, 0.20, 0.20, 0.15, 0.15, 0.10]
    overall_score = sum(d["score"] * w for d, w in zip(dims, weights))

    def _grade(s):
        if s >= 85: return "S"
        if s >= 70: return "A"
        if s >= 55: return "B"
        if s >= 40: return "C"
        return "D"

    for d in dims:
        d["grade"] = _grade(d["score"])

    overall_grade = _grade(overall_score)
    weakest = min(dims, key=lambda d: d["score"])
    strongest = max(dims, key=lambda d: d["score"])

    summary_text = _build_summary_text(analytics, overall_grade, overall_score, dims, weakest)

    return {
        "overall": overall_grade,
        "score": round(overall_score, 1),
        "dimensions": dims,
        "weakest": weakest["name"],
        "strongest": strongest["name"],
        "summary_text": summary_text,
    }


def _build_summary_text(analytics, grade, score, dims, weakest):
    """Generate one-sentence strategy summary based on grade and metrics."""
    ann_ret = analytics.get("annual_return", 0)
    max_dd = analytics.get("max_drawdown", 0)
    sharpe = analytics.get("sharpe_ratio", 0)
    bench_ret = analytics.get("benchmark_return", 0)
    excess = analytics.get("excess_return", 0)

    if grade in ("S", "A"):
        prefix = "策略表现优异" if grade == "S" else "策略表现良好"
        body = (f"年化 {ann_ret:+.1%}，最大回撤 {max_dd:.1%}，"
                f"Sharpe {sharpe:.2f} 体现出色的风险调整收益")
        if excess > 0:
            body += f"，超额收益 {excess:+.1%} 跑赢基准"
        return f"{prefix}：{body}。"
    elif grade == "B":
        return (f"策略表现中等：年化 {ann_ret:+.1%}，但回撤 {max_dd:.1%} 偏大。"
                f"Sharpe {sharpe:.2f}，建议关注{weakest['name']}维度。")
    else:
        beat = "跑赢" if excess > 0 else "未能跑赢"
        return (f"策略表现欠佳：年化 {ann_ret:+.1%} {beat}基准 ({bench_ret:+.1%})，"
                f"最大回撤 {max_dd:.1%}。优先改善{weakest['name']}维度。")
```

- [ ] **Step 2: Add diagnose_bottleneck()**

Append to `eqlib/attribution.py`:

```python
def diagnose_bottleneck(analytics, grade_info) -> list:
    """Identify failing metrics and root causes.

    Args:
        analytics: dict from analyze_returns()
        grade_info: dict from grade_strategy()

    Returns:
        list of diagnostic dicts with keys: metric, severity, finding,
        root_cause, affected_period, related_metrics.
    """
    if analytics is None or grade_info is None:
        return []

    diagnostics = []
    from eqlib.constants import RISK_FREE_RATE

    targets = {
        "sharpe_ratio": 1.0,
        "max_drawdown": -0.20,
        "annual_return": 0.0,
        "win_rate_trade": 0.40,
        "alpha": 0.0,
    }

    # Max drawdown check
    max_dd = analytics.get("max_drawdown", 0)
    if max_dd < targets["max_drawdown"]:
        dd_start = str(analytics.get("max_drawdown_start", ""))
        dd_end = str(analytics.get("max_drawdown_end", ""))
        # Find worst single trade
        per_stock = analytics.get("per_stock_pnl", {})
        worst_stock = min(per_stock.values()) if per_stock else 0
        consecutive_loss = 0
        max_consec = 0
        mr = analytics.get("monthly_returns", {})
        for v in mr.values():
            if v < 0:
                consecutive_loss += 1
                max_consec = max(max_consec, consecutive_loss)
            else:
                consecutive_loss = 0
        diagnostics.append({
            "metric": "max_drawdown",
            "severity": "critical" if max_dd < -0.25 else "warning",
            "finding": f"最大回撤 {max_dd:.1%} 超出 {abs(targets['max_drawdown']):.0%} 容忍线",
            "root_cause": f"回撤期间未能及时减仓，单笔最大亏损占总资产比例过高",
            "affected_period": f"{dd_start} to {dd_end}",
            "related_metrics": {
                "worst_stock_pnl": round(worst_stock, 2),
                "max_consecutive_loss_months": max_consec,
                "max_loss_in_drawdown": round(max_dd, 4),
            },
        })

    # Sharpe check
    sharpe = analytics.get("sharpe_ratio", 0)
    if sharpe < targets["sharpe_ratio"]:
        diagnostics.append({
            "metric": "sharpe_ratio",
            "severity": "warning",
            "finding": f"Sharpe {sharpe:.2f} 低于 1.0 目标",
            "root_cause": "收益波动过大或收益率偏低，需优化入场信号或降低仓位波动",
            "affected_period": "full period",
            "related_metrics": {
                "annual_volatility": round(analytics.get("annual_volatility", 0), 4),
                "annual_return": round(analytics.get("annual_return", 0), 4),
            },
        })

    # Win rate check
    win_rate = analytics.get("win_rate_trade", 0)
    if analytics.get("trade_count", 0) >= 3 and win_rate < targets["win_rate_trade"]:
        diagnostics.append({
            "metric": "win_rate_trade",
            "severity": "warning",
            "finding": f"胜率 {win_rate:.0%} 低于 40% 目标",
            "root_cause": "入场信号质量不足，建议增加确认指标或收紧入场条件",
            "affected_period": "full period",
            "related_metrics": {
                "win_count": analytics.get("win_count", 0),
                "loss_count": analytics.get("loss_count", 0),
                "profit_loss_ratio": round(analytics.get("profit_loss_ratio", 0), 2),
            },
        })

    # Alpha check
    alpha_val = analytics.get("alpha", 0)
    if alpha_val < 0:
        diagnostics.append({
            "metric": "alpha",
            "severity": "warning",
            "finding": f"Alpha {alpha_val:+.2%} 为负，策略未能产生超额收益",
            "root_cause": "入场信号或持仓周期需优化，当前策略相对基准无信息优势",
            "affected_period": "full period",
            "related_metrics": {
                "beta": round(analytics.get("beta", 0), 3),
                "excess_return": round(analytics.get("excess_return", 0), 4),
            },
        })

    return diagnostics
```

- [ ] **Step 3: Add recommend_params()**

Append to `eqlib/attribution.py`:

```python
def recommend_params(analytics, grade_info, current_params=None, param_ranges=None) -> list:
    """Suggest parameter adjustments based on diagnostics.

    Args:
        analytics: dict from analyze_returns()
        grade_info: dict from grade_strategy()
        current_params: dict of current PARAMS from strategy file (optional)
        param_ranges: dict of PARAM_RANGES from strategy file (optional)

    Returns:
        list of recommendation dicts with keys: priority, target_metric,
        action, parameter, current, suggested, range, rationale,
        expected_effect, risk.
    """
    if current_params is None or param_ranges is None:
        return []

    recommendations = []
    priority = 0

    max_dd = analytics.get("max_drawdown", 0) if analytics else 0
    sharpe = analytics.get("sharpe_ratio", 0) if analytics else 0
    win_rate = analytics.get("win_rate_trade", 0) if analytics else 0
    trade_count = analytics.get("trade_count", 0) if analytics else 0

    # Rule 1: Drawdown too large → tighten stop-loss
    if max_dd < -0.20 and "stop_loss_pct" in current_params and "stop_loss_pct" in param_ranges:
        priority += 1
        cur = current_params["stop_loss_pct"]
        lo, hi, step = param_ranges["stop_loss_pct"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "max_drawdown",
                "action": "decrease",
                "parameter": "stop_loss_pct",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": f"止损线从 {cur:.0%} 收紧至 {suggested:.0%}，在回撤早期截断亏损",
                "expected_effect": "max_drawdown 预计改善 3-5%",
                "risk": "可能增加止损触发频率，降低胜率 2-3%",
            })

    # Rule 2: Drawdown too large → reduce position size
    if max_dd < -0.20 and "position_pct" in current_params and "position_pct" in param_ranges:
        priority += 1
        cur = current_params["position_pct"]
        lo, hi, step = param_ranges["position_pct"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "max_drawdown",
                "action": "decrease",
                "parameter": "position_pct",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": f"单票仓位从 {cur:.0%} 降至 {suggested:.0%}，分散风险",
                "expected_effect": "max_drawdown 预计改善 4-6%",
                "risk": "收益绝对值会降低 2-4%",
            })

    # Rule 3: Sharpe too low → increase volatility confirmation
    if sharpe < 1.0 and "vol_confirm_mul" in current_params and "vol_confirm_mul" in param_ranges:
        priority += 1
        cur = current_params["vol_confirm_mul"]
        lo, hi, step = param_ranges["vol_confirm_mul"]
        suggested = min(hi, round(cur + step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "sharpe_ratio",
                "action": "increase",
                "parameter": "vol_confirm_mul",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "提高波动确认阈值，过滤低质量入场信号",
                "expected_effect": "Sharpe 预计提升 0.1-0.3",
                "risk": "交易次数可能减少",
            })

    # Rule 4: Win rate too low → widen RSI bands or tighten entry
    if win_rate < 0.40 and trade_count >= 3 and "rsi_oversold" in current_params and "rsi_oversold" in param_ranges:
        priority += 1
        cur = current_params["rsi_oversold"]
        lo, hi, step = param_ranges["rsi_oversold"]
        suggested = max(lo, round(cur - step))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "win_rate_trade",
                "action": "decrease",
                "parameter": "rsi_oversold",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "降低 RSI 超卖阈值，只在更极端的超卖区域入场",
                "expected_effect": "胜率预计提升 3-5%",
                "risk": "交易次数可能减少",
            })

    # Rule 5: Too few trades → decrease vol_confirm_mul
    if trade_count < 3 and "vol_confirm_mul" in current_params and "vol_confirm_mul" in param_ranges:
        priority += 1
        cur = current_params["vol_confirm_mul"]
        lo, hi, step = param_ranges["vol_confirm_mul"]
        suggested = max(lo, round(cur - step, 4))
        if suggested != cur:
            recommendations.append({
                "priority": priority,
                "target_metric": "trade_count",
                "action": "decrease",
                "parameter": "vol_confirm_mul",
                "current": cur,
                "suggested": suggested,
                "range": [lo, hi],
                "rationale": "降低波动确认倍数以产生更多交易信号",
                "expected_effect": "交易次数预计增加",
                "risk": "可能引入低质量交易",
            })

    return recommendations
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from eqlib.attribution import grade_strategy, diagnose_bottleneck, recommend_params; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add eqlib/attribution.py
git commit -m "feat: add grade_strategy(), diagnose_bottleneck(), recommend_params() to attribution.py"
```

---

### Task 4: Export New Functions in __init__.py

**Files:**
- Modify: `eqlib/__init__.py:187,302` (add 3 exports)

- [ ] **Step 1: Add imports and exports**

In `eqlib/__init__.py`, find the line:
```python
from eqlib.report import generate_chart, generate_report_md, generate_report_json, generate_html_report
```
Change to:
```python
from eqlib.report import generate_chart, generate_report_md, generate_report_json, generate_html_report
from eqlib.attribution import grade_strategy, diagnose_bottleneck, recommend_params
```

Find `"generate_chart"` in the `__all__` list and add after the report exports:
```python
    "grade_strategy", "diagnose_bottleneck", "recommend_params",
```

- [ ] **Step 2: Verify**

Run: `python -c "from eqlib import grade_strategy, diagnose_bottleneck, recommend_params; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add eqlib/__init__.py
git commit -m "feat: export grade_strategy, diagnose_bottleneck, recommend_params"
```

---

### Task 5: Write Tests for New Attribution Functions

**Files:**
- Create: `tests/test_attribution_grading.py` (~120 lines)

- [ ] **Step 1: Write the test file**

```python
"""Tests for grade_strategy(), diagnose_bottleneck(), recommend_params()."""

import pytest
from eqlib.attribution import grade_strategy, diagnose_bottleneck, recommend_params


def _make_analytics(**overrides):
    """Build a minimal analytics dict for grading tests."""
    base = {
        "total_return": 0.15,
        "annual_return": 0.15,
        "annual_volatility": 0.18,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.8,
        "max_drawdown": -0.12,
        "max_drawdown_start": "2024-03-15",
        "max_drawdown_end": "2024-04-02",
        "calmar_ratio": 1.25,
        "alpha": 0.05,
        "beta": 0.8,
        "information_ratio": 0.9,
        "win_rate": 0.55,
        "win_rate_daily": 0.55,
        "win_rate_trade": 0.60,
        "trade_count": 20,
        "win_count": 12,
        "loss_count": 8,
        "profit_loss_ratio": 2.0,
        "annual_turnover": 3.0,
        "total_commission": 200.0,
        "net_return": 0.15,
        "trading_days": 252,
        "num_trades": 40,
        "excess_return": 0.07,
        "benchmark_return": 0.08,
        "excess_return_max_drawdown": -0.05,
        "excess_return_sharpe": 0.9,
        "daily_excess_return": 0.0003,
        "benchmark_volatility": 0.15,
        "monthly_returns": {"2024-01": 0.03, "2024-02": -0.01, "2024-03": 0.04,
                            "2024-04": 0.01, "2024-05": -0.02, "2024-06": 0.06,
                            "2024-07": 0.008, "2024-08": -0.003, "2024-09": 0.02,
                            "2024-10": 0.05, "2024-11": -0.01, "2024-12": 0.03},
        "rolling_sharpe_60d": [],
        "rolling_volatility_60d": [],
        "daily_returns_stats": {},
        "per_stock_pnl": {"000001": 5000.0, "600036": -1000.0},
        "drawdown_periods": [],
    }
    base.update(overrides)
    return base


class TestGradeStrategy:
    def test_returns_none_for_none_input(self):
        result = grade_strategy(None)
        assert result["overall"] == "D"
        assert result["score"] == 0

    def test_six_dimensions_present(self):
        g = grade_strategy(_make_analytics())
        assert len(g["dimensions"]) == 6
        names = [d["name"] for d in g["dimensions"]]
        assert "return_capability" in names
        assert "risk_control" in names
        assert "risk_adjusted" in names
        assert "trade_quality" in names
        assert "excess_capability" in names
        assert "stability" in names

    def test_grade_s_for_excellent_strategy(self):
        g = grade_strategy(_make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70, profit_loss_ratio=3.0,
            excess_return=0.15, information_ratio=1.5,
        ))
        assert g["overall"] in ("S", "A")
        assert g["score"] >= 70

    def test_grade_d_for_poor_strategy(self):
        g = grade_strategy(_make_analytics(
            annual_return=-0.10, sharpe_ratio=-0.5, max_drawdown=-0.40,
            alpha=-0.05, win_rate_trade=0.20, excess_return=-0.15,
        ))
        assert g["overall"] in ("C", "D")

    def test_weakest_and_strongest_identified(self):
        g = grade_strategy(_make_analytics())
        assert g["weakest"] != ""
        assert g["strongest"] != ""
        assert g["weakest"] != g["strongest"]

    def test_summary_text_nonempty(self):
        g = grade_strategy(_make_analytics())
        assert len(g["summary_text"]) > 10

    def test_each_dimension_has_grade(self):
        g = grade_strategy(_make_analytics())
        for d in g["dimensions"]:
            assert "grade" in d
            assert d["grade"] in ("S", "A", "B", "C", "D")

    def test_monthly_win_rate_calculation(self):
        """9 positive months out of 12 = 75%."""
        g = grade_strategy(_make_analytics())
        stability = [d for d in g["dimensions"] if d["name"] == "stability"][0]
        assert stability["key"]["monthly_win_rate"] == pytest.approx(0.75, abs=0.01)


class TestDiagnoseBottleneck:
    def test_empty_for_none_input(self):
        assert diagnose_bottleneck(None, None) == []

    def test_detects_drawdown_violation(self):
        a = _make_analytics(max_drawdown=-0.28)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        metrics = [x["metric"] for x in d]
        assert "max_drawdown" in metrics

    def test_detects_low_sharpe(self):
        a = _make_analytics(sharpe_ratio=0.3)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        metrics = [x["metric"] for x in d]
        assert "sharpe_ratio" in metrics

    def test_no_diagnostics_for_excellent_strategy(self):
        a = _make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70,
        )
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        assert len(d) == 0

    def test_diagnostic_has_required_keys(self):
        a = _make_analytics(max_drawdown=-0.30)
        g = grade_strategy(a)
        d = diagnose_bottleneck(a, g)
        for item in d:
            assert "metric" in item
            assert "severity" in item
            assert "finding" in item
            assert "root_cause" in item


class TestRecommendParams:
    def test_empty_when_no_params_provided(self):
        assert recommend_params(_make_analytics(), {}, None, None) == []

    def test_recommends_stop_loss_for_drawdown(self):
        a = _make_analytics(max_drawdown=-0.28)
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.08, "position_pct": 0.80}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02), "position_pct": (0.20, 1.00, 0.10)}
        recs = recommend_params(a, g, params, ranges)
        sl_recs = [r for r in recs if r["parameter"] == "stop_loss_pct"]
        assert len(sl_recs) >= 1
        assert sl_recs[0]["suggested"] < sl_recs[0]["current"]

    def test_recommends_vol_confirm_for_low_sharpe(self):
        a = _make_analytics(sharpe_ratio=0.4)
        g = grade_strategy(a)
        params = {"vol_confirm_mul": 1.0}
        ranges = {"vol_confirm_mul": (0.5, 3.0, 0.5)}
        recs = recommend_params(a, g, params, ranges)
        vc_recs = [r for r in recs if r["parameter"] == "vol_confirm_mul"]
        assert len(vc_recs) >= 1
        assert vc_recs[0]["suggested"] > vc_recs[0]["current"]

    def test_recommendation_has_required_keys(self):
        a = _make_analytics(max_drawdown=-0.30)
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.10}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02)}
        recs = recommend_params(a, g, params, ranges)
        for r in recs:
            assert "priority" in r
            assert "parameter" in r
            assert "current" in r
            assert "suggested" in r
            assert "rationale" in r

    def test_no_recommendation_when_all_pass(self):
        a = _make_analytics(
            annual_return=0.25, sharpe_ratio=2.0, max_drawdown=-0.08,
            alpha=0.10, win_rate_trade=0.70,
        )
        g = grade_strategy(a)
        params = {"stop_loss_pct": 0.05, "position_pct": 0.50}
        ranges = {"stop_loss_pct": (0.02, 0.30, 0.02), "position_pct": (0.20, 1.00, 0.10)}
        recs = recommend_params(a, g, params, ranges)
        assert len(recs) == 0
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/test_attribution_grading.py -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_attribution_grading.py
git commit -m "test: add tests for grade_strategy, diagnose_bottleneck, recommend_params"
```

---

### Task 6: Add Report Helpers — _calc_strategy_score() and _build_summary_text()

**Files:**
- Modify: `eqlib/report.py` (add ~20 lines before `generate_html_report`)

- [ ] **Step 1: Add helper function in report.py**

Insert before the `generate_html_report` function definition (around line 690):

```python
def _calc_strategy_score(analytics):
    """Compute grade info for HTML/MD report display.

    Wraps grade_strategy() from attribution with graceful fallback.
    """
    from eqlib.attribution import grade_strategy
    try:
        return grade_strategy(analytics)
    except Exception:
        return {"overall": "N/A", "score": 0, "dimensions": [],
                "weakest": "", "strongest": "", "summary_text": ""}
```

- [ ] **Step 2: Update _calc_metrics() to include grade data**

In the `_calc_metrics()` function (line 928), add to the return dict after `"trade_count"`:

```python
        # Grade data for HTML template
        "grade_data": _calc_strategy_score(analytics),
```

And add `"grade_data": None,` to the fallback return dict (the N/A dict at line 938).

- [ ] **Step 3: Verify no import errors**

Run: `python -c "from eqlib.report import _calc_strategy_score; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add eqlib/report.py
git commit -m "feat: add _calc_strategy_score() helper and grade_data to _calc_metrics()"
```

---

### Task 7: Rewrite generate_report_json() — Agent-First Structure

**Files:**
- Modify: `eqlib/report.py:2807-2993` (replace `generate_report_json` function entirely)

- [ ] **Step 1: Replace generate_report_json()**

Replace the entire `generate_report_json` function (lines 2807-2993) with:

```python
def generate_report_json(result, out_path, *,
                         strategy_params=None,
                         iteration_context=None):
    """Generate Agent-First JSON report with verdict/targets/diagnostics/recommendations.

    Args:
        result: dict from run_backtest()
        out_path: output file path
        strategy_params: {"current": {...}, "constraints": [...]} or None
        iteration_context: {"run_id": "...", "previous_run_id": "...",
                            "changes_applied": {...}, "previous_metrics": {...}} or None
    """
    from eqlib.attribution import (
        analyze_returns, brinson_attribution, fama_french_analysis,
        grade_strategy, diagnose_bottleneck, recommend_params,
    )

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)

    # Benchmark data
    bench_return = None
    try:
        from eqlib.data import fetch_stock_data
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_return = float(bench_df["close"].iloc[-1] / bench_df["close"].iloc[0] - 1)
    except Exception:
        pass

    # Cumulative return series
    pf_entries = sorted(
        recorded.values(), key=lambda x: x.get("date", datetime.date.min)
    ) if isinstance(recorded, dict) else recorded
    cumulative_returns = []
    for r in pf_entries:
        if "total_value" in r:
            cumulative_returns.append({
                "date": str(r["date"]),
                "total_value": round(r["total_value"], 2),
                "cumulative_return": round(r["total_value"] / initial - 1, 6) if initial > 0 else 0.0,
            })

    # Chart data for native rendering
    chart = _compute_chart_data(result)

    # ── Layer 1: verdict ────────────────────────────────────────────
    targets_def = {
        "sharpe_ratio": {"op": ">=", "threshold": 1.0},
        "max_drawdown": {"op": ">=", "threshold": -0.20},
        "annual_return": {"op": ">=", "threshold": 0.0},
        "win_rate_trade": {"op": ">=", "threshold": 0.40},
        "alpha": {"op": ">=", "threshold": 0.0},
        "beta": {"op": "between", "threshold": [0.3, 1.3]},
        "trade_count": {"op": ">=", "threshold": 3},
    }

    # ── Layer 2: targets ────────────────────────────────────────────
    targets = []
    all_pass = True
    priority_counter = 0
    for metric_name, target_def in targets_def.items():
        value = analytics.get(metric_name, 0) if analytics else 0
        op = target_def["op"]
        threshold = target_def["threshold"]
        if op == ">=":
            passed = value >= threshold
            gap = f"{value - threshold:+.4f}" if isinstance(value, (int, float)) else str(value)
        elif op == "between":
            lo, hi = threshold
            passed = lo <= value <= hi
            gap = "in range" if passed else f"out of [{lo}, {hi}]"
        else:
            passed = True
            gap = "N/A"

        if not passed:
            all_pass = False
            priority_counter += 1
            targets.append({
                "metric": metric_name, "value": value,
                "target": target_def, "pass": False,
                "gap": gap, "priority": priority_counter,
            })
        else:
            targets.append({
                "metric": metric_name, "value": value,
                "target": target_def, "pass": True,
                "gap": gap, "priority": None,
            })

    # Sort: failing first by priority, then passing
    targets.sort(key=lambda t: (t["pass"], t.get("priority") or 999))

    bottleneck = grade_info.get("weakest", "") if not all_pass else None
    action = "complete" if all_pass else "adjust_params"
    verdict = {
        "pass": all_pass,
        "grade": grade_info["overall"],
        "score": grade_info["score"],
        "bottleneck": bottleneck,
        "action": action,
        "summary": grade_info.get("summary_text", ""),
    }

    # ── Layer 3: diagnostics ────────────────────────────────────────
    diagnostics = diagnose_bottleneck(analytics, grade_info) if analytics else []

    # ── Layer 4: recommendations ────────────────────────────────────
    current_p = strategy_params.get("current", {}) if strategy_params else None
    ranges_p = strategy_params.get("ranges", {}) if strategy_params else None
    recommendations = recommend_params(analytics, grade_info, current_p, ranges_p)

    # ── Layer 6: iteration ──────────────────────────────────────────
    iteration = None
    if iteration_context:
        prev_metrics = iteration_context.get("previous_metrics", {})
        metric_deltas = {}
        for key in ["annual_return", "sharpe_ratio", "max_drawdown",
                     "annual_volatility", "win_rate_trade"]:
            cur_val = analytics.get(key, 0) if analytics else 0
            prev_val = prev_metrics.get(key, None)
            if prev_val is not None:
                delta = cur_val - prev_val
                improved = (delta > 0) if key != "max_drawdown" else (delta > 0)
                if key == "annual_volatility":
                    improved = delta < 0
                metric_deltas[key] = {
                    "from": prev_val, "to": cur_val,
                    "delta": f"{delta:+.4f}", "improved": improved,
                }
        prev_score = prev_metrics.get("_grade_score", 0)
        score_delta = grade_info["score"] - prev_score
        regression = any(
            not v["improved"] for k, v in metric_deltas.items()
            if k in ("annual_return", "sharpe_ratio", "max_drawdown")
        )
        iteration = {
            "run_id": iteration_context.get("run_id", ""),
            "previous_run_id": iteration_context.get("previous_run_id", ""),
            "changes_applied": iteration_context.get("changes_applied", {}),
            "score_delta": score_delta,
            "previous_grade": prev_metrics.get("_grade", ""),
            "metric_deltas": metric_deltas,
            "regression_detected": regression,
            "convergence_note": "",
        }

    # ── Build final report ──────────────────────────────────────────
    report = {
        "verdict": verdict,
        "targets": targets,
        "diagnostics": diagnostics,
        "recommendations": recommendations,
    }

    if strategy_params:
        report["strategy_params"] = strategy_params

    if iteration:
        report["iteration"] = iteration

    report["grade"] = grade_info

    # Raw metrics
    if analytics:
        report["metrics"] = {
            k: round(v, 6) if isinstance(v, float) else v
            for k, v in analytics.items()
            if isinstance(v, (int, float, str, bool))
        }
        report["time_series"] = {
            "monthly_returns": analytics.get("monthly_returns", {}),
            "rolling_sharpe_60d": analytics.get("rolling_sharpe_60d", []),
            "rolling_volatility_60d": analytics.get("rolling_volatility_60d", []),
            "drawdown_periods": analytics.get("drawdown_periods", []),
        }
        report["daily_returns_stats"] = analytics.get("daily_returns_stats", {})
        report["per_stock_pnl"] = {
            k: round(v, 2) for k, v in analytics.get("per_stock_pnl", {}).items()
        }
    else:
        report["metrics"] = None
        report["time_series"] = {}
        report["daily_returns_stats"] = {}
        report["per_stock_pnl"] = {}

    report["summary"] = {
        "start_date": str(ctx.start_date),
        "end_date": str(ctx.end_date),
        "initial_capital": initial,
        "final_value": round(final, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "num_trades": len(trade_log),
        "securities": list(set(t["security"] for t in trade_log) or []),
        "benchmark": benchmark,
        "benchmark_return": round(bench_return, 4) if bench_return is not None else None,
    }

    report["trades"] = [
        {
            "type": t["type"], "date": str(t["date"]),
            "security": t["security"], "price": t["price"],
            "amount": t["amount"], "commission": round(t.get("commission", 0), 2),
        }
        for t in trade_log
    ]

    report["positions"] = {
        sec: {
            "amount": pos.amount,
            "avg_cost": round(pos.avg_cost, 3),
            "total_value": round(pos.total_value, 2),
        }
        for sec, pos in ctx.portfolio.positions.items()
        if pos.amount > 0
    }

    # Chart data
    report["chart_data"] = {
        "candlestick_data": chart["candlestick_data"],
        "volume_data": chart["volume_data"],
        "cum_return_data": chart["cum_return_data"],
        "drawdown_data": chart["drawdown_data"],
    }

    # Factor analysis
    ff = fama_french_analysis(result)
    if ff:
        report["factor_analysis"] = {
            k: round(v, 4) if isinstance(v, float) else v for k, v in ff.items()
        }

    br = brinson_attribution(result)
    if br:
        report["brinson_attribution"] = {
            k: round(v, 4) if isinstance(v, float) else v for k, v in br.items()
        }

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Data saved: {out_path}")
```

- [ ] **Step 2: Update examples/05_reports.py for new JSON keys**

In `examples/05_reports.py`, the section that reads the JSON report checks for `"risk_metrics"` and `"benchmark_comparison"` keys. Update lines 157-173 to use the new keys:

Change:
```python
    if "risk_metrics" in report:
        print(f"\n  Risk metrics:")
        for key, val in report["risk_metrics"].items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")

    if "benchmark_comparison" in report:
        bm = report["benchmark_comparison"]
        print(f"\n  Benchmark comparison:")
        for key, val in bm.items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")
```
To:
```python
    if "verdict" in report:
        v = report["verdict"]
        print(f"\n  Verdict: Grade {v['grade']} ({v['score']}/100) — {'PASS' if v['pass'] else 'FAIL'}")
        print(f"  Summary: {v['summary']}")

    if "targets" in report:
        print(f"\n  Targets:")
        for t in report["targets"][:5]:
            status = "PASS" if t["pass"] else "FAIL"
            print(f"    {t['metric']}: {t['value']} [{status}]")

    if "metrics" in report and report["metrics"]:
        print(f"\n  Key metrics:")
        for key in ["annual_return", "sharpe_ratio", "max_drawdown", "alpha", "beta"]:
            val = report["metrics"].get(key)
            if val is not None:
                print(f"    {key}: {val:.4f}" if isinstance(val, float) else f"    {key}: {val}")
```

- [ ] **Step 3: Run smoke test**

Run: `python examples/05_reports.py`
Expected: All 4 reports generated, JSON output shows verdict/targets/metrics

- [ ] **Step 4: Commit**

```bash
git add eqlib/report.py examples/05_reports.py
git commit -m "feat: rewrite generate_report_json() with Agent-First structure"
```

---

### Task 8: Restructure generate_report_md()

**Files:**
- Modify: `eqlib/report.py:2570-2805` (replace `generate_report_md` function)

- [ ] **Step 1: Replace generate_report_md()**

Replace the entire `generate_report_md` function (lines 2570-2805) with:

```python
def generate_report_md(result, out_path):
    """Generate professional Markdown report with grade breakdown,
    monthly returns, rolling metrics, and top drawdown periods.
    """
    from eqlib.attribution import (
        analyze_returns, brinson_attribution, fama_french_analysis, grade_strategy,
    )
    from eqlib.data import fetch_stock_data

    ctx = result["context"]
    trade_log = result["trade_log"]
    benchmark = result.get("benchmark", "000300.XSHG")

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)

    bench_data = {}
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_init = bench_df["close"].iloc[0]
            bench_final = bench_df["close"].iloc[-1]
            bench_data["return"] = (bench_final - bench_init) / bench_init * 100
    except Exception:
        pass

    bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")
    lines = []

    # ── Header ──────────────────────────────────────────────────────
    lines.append(f"# Backtest Report — {list(set(t['security'] for t in trade_log) or ['N/A'])[0]}")
    lines.append("")
    lines.append(f"*Generated by {BRAND_NAME} · {ctx.start_date} to {ctx.end_date} · "
                 f"Grade: {grade_info['overall']} ({grade_info['score']}/100)*")
    lines.append("")

    # ── Strategy Summary ────────────────────────────────────────────
    lines.append("## Strategy Summary")
    lines.append("")
    lines.append(f"> {grade_info.get('summary_text', 'N/A')}")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **Period** | {ctx.start_date} to {ctx.end_date} |")
    lines.append(f"| **Initial Capital** | {initial:,.2f} |")
    lines.append(f"| **Final Value** | {final:,.2f} |")
    lines.append(f"| **P&L** | {pnl:+,.2f} ({pnl_pct:+.2f}%) |")
    lines.append(f"| **Benchmark** | {bench_label} |")
    if bench_data:
        lines.append(f"| **Benchmark Return** | {bench_data['return']:+.2f}% |")
    lines.append("")

    # ── Grade Breakdown ─────────────────────────────────────────────
    lines.append("## Grade Breakdown")
    lines.append("")
    lines.append("| Dimension | Score | Grade | Key Metric |")
    lines.append("|-----------|-------|-------|------------|")
    for d in grade_info.get("dimensions", []):
        key_str = ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                           for k, v in d.get("key", {}).items())
        lines.append(f"| {d['name']} | {d['score']:.0f} | {d.get('grade', 'N/A')} | {key_str} |")
    lines.append(f"| **Overall** | **{grade_info['score']:.0f}** | **{grade_info['overall']}** | |")
    lines.append("")

    # ── Performance Metrics ─────────────────────────────────────────
    if analytics:
        lines.append("## Performance Metrics")
        lines.append("")
        lines.append("| Metric | Value | Benchmark | Delta |")
        lines.append("|--------|-------|-----------|-------|")
        ann_ret = analytics["annual_return"]
        bench_ret_pct = bench_data.get("return", 0) / 100
        lines.append(f"| Annual Return | {ann_ret:+.2%} | {bench_ret_pct:+.2%} | {ann_ret - bench_ret_pct:+.2%} |")
        lines.append(f"| Annual Volatility | {analytics['annual_volatility']:.2%} | {analytics.get('benchmark_volatility', 0):.2%} | |")
        lines.append(f"| Sharpe Ratio | {analytics['sharpe_ratio']:.2f} | — | — |")
        lines.append(f"| Sortino Ratio | {analytics['sortino_ratio']:.2f} | — | — |")
        lines.append(f"| Max Drawdown | {analytics['max_drawdown']:.2%} | — | — |")
        lines.append(f"| Calmar Ratio | {analytics['calmar_ratio']:.2f} | — | — |")
        lines.append(f"| Alpha | {analytics['alpha']:+.2%} | — | — |")
        lines.append(f"| Beta | {analytics['beta']:.2f} | — | — |")
        lines.append(f"| Information Ratio | {analytics['information_ratio']:.2f} | — | — |")
        lines.append(f"| Win Rate (trade) | {analytics['win_rate_trade']:.1%} | — | — |")
        lines.append(f"| Profit/Loss Ratio | {'∞' if analytics.get('profit_loss_ratio', 0) == float('inf') else f'{analytics.get(\"profit_loss_ratio\", 0):.2f}'} | — | — |")
        lines.append(f"| Trade Count | {analytics['trade_count']} | — | — |")
        lines.append("")

    # ── Monthly Returns ─────────────────────────────────────────────
    if analytics and analytics.get("monthly_returns"):
        lines.append("## Monthly Returns")
        lines.append("")
        mr = analytics["monthly_returns"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        lines.append("| Year | " + " | ".join(months) + " | YTD |")
        lines.append("|------|" + "|".join(["-----"] * 12) + "|-----|")
        years = sorted(set(k[:4] for k in mr.keys()))
        for year in years:
            row = [year]
            for m in range(1, 13):
                key = f"{year}-{m:02d}"
                val = mr.get(key)
                row.append(f"{val:+.1%}" if val is not None else "—")
            ytd_vals = [v for k, v in mr.items() if k.startswith(year)]
            ytd = 1.0
            for v in ytd_vals:
                ytd *= (1 + v)
            ytd -= 1
            row.append(f"{ytd:+.1%}")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # ── Rolling Metrics ─────────────────────────────────────────────
    if analytics and analytics.get("rolling_sharpe_60d"):
        lines.append("## Rolling Metrics (60-day window, quarterly sampled)")
        lines.append("")
        lines.append("| Date | Rolling Sharpe | Rolling Vol |")
        lines.append("|------|---------------|-------------|")
        rs = analytics["rolling_sharpe_60d"]
        rv = analytics["rolling_volatility_60d"]
        # Sample every ~63 trading days (quarterly)
        step = max(1, len(rs) // 4)
        for i in range(0, len(rs), step):
            date = rs[i]["date"]
            sharpe_val = rs[i]["value"]
            vol_val = rv[i]["value"] if i < len(rv) else 0
            lines.append(f"| {date} | {sharpe_val:.2f} | {vol_val:.1%} |")
        lines.append("")

    # ── Top 5 Drawdown Periods ──────────────────────────────────────
    if analytics and analytics.get("drawdown_periods"):
        lines.append("## Top 5 Drawdown Periods")
        lines.append("")
        lines.append("| # | Start | Trough | Recovery | Depth | Duration |")
        lines.append("|---|-------|--------|----------|-------|----------|")
        for dp in analytics["drawdown_periods"]:
            recovery = dp.get("recovery") or "ongoing"
            duration = f"{dp['duration_days']}d"
            lines.append(f"| {dp['rank']} | {dp['start']} | {dp['trough']} | "
                        f"{recovery} | {dp['depth']:.1%} | {duration} |")
        lines.append("")

    # ── Trade Analysis ──────────────────────────────────────────────
    lines.append("## Trade Analysis")
    lines.append("")
    buy_count = sum(1 for t in trade_log if t["type"] == "BUY")
    sell_count = sum(1 for t in trade_log if t["type"] == "SELL")
    total_commission = sum(t.get("commission", 0) for t in trade_log)
    lines.append(f"- Buy orders: {buy_count}")
    lines.append(f"- Sell orders: {sell_count}")
    lines.append(f"- Total commission: {total_commission:,.2f}")
    lines.append(f"- Securities traded: {len(set(t['security'] for t in trade_log))}")
    lines.append("")

    if analytics and analytics.get("per_stock_pnl"):
        lines.append("### Per-Stock P&L")
        lines.append("")
        lines.append("| Security | P&L |")
        lines.append("|----------|-----|")
        for sec, pnl_val in sorted(analytics["per_stock_pnl"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {sec} | {pnl_val:+,.2f} |")
        lines.append("")

    # ── Trade P&L ───────────────────────────────────────────────────
    if trade_log:
        lines.append("## Trade P&L")
        lines.append("")
        lines.append("| # | Security | Buy Date | Buy Price | Sell Date | Sell Price | P&L |")
        lines.append("|---|----------|----------|-----------|-----------|------------|-----|")
        trade_pairs = {}
        trade_num = 0
        for t in trade_log:
            sec = t["security"]
            if sec not in trade_pairs:
                trade_pairs[sec] = []
            if t["type"] == "BUY":
                trade_pairs[sec].append(t)
            elif t["type"] == "SELL" and trade_pairs[sec]:
                buy_t = trade_pairs[sec].pop(0)
                buy_val = buy_t["price"] * buy_t["amount"] + buy_t.get("commission", 0)
                sell_val = t["price"] * t["amount"] - t.get("commission", 0)
                trade_pnl = sell_val - buy_val
                trade_num += 1
                lines.append(
                    f"| {trade_num} | {sec} | {buy_t['date']} | {buy_t['price']:.3f} "
                    f"| {t['date']} | {t['price']:.3f} | {trade_pnl:+,.0f} |"
                )
        lines.append("")

    # ── Factor Analysis ─────────────────────────────────────────────
    ff = fama_french_analysis(result)
    if ff:
        lines.append("## Factor Analysis")
        lines.append("")
        lines.append("| Factor | Value |")
        lines.append("|--------|-------|")
        for k, v in ff.items():
            if isinstance(v, float):
                lines.append(f"| {k} | {v:.4f} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")

    # ── Brinson Attribution ─────────────────────────────────────────
    br = brinson_attribution(result)
    if br:
        lines.append("## Brinson Attribution")
        lines.append("")
        lines.append("| Component | Effect |")
        lines.append("|-----------|--------|")
        for k, v in br.items():
            if isinstance(v, float):
                lines.append(f"| {k} | {v:+.2%} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")

    # ── Data Sources ────────────────────────────────────────────────
    lines.append("## Data Sources")
    lines.append("")
    lines.append("| Source | Details |")
    lines.append("|--------|---------|")
    lines.append("| Market Data | AKShare `stock_zh_a_hist` (EastMoney), forward-adjusted daily OHLCV |")
    lines.append("| Benchmark | CSI 300 / SSE Composite via AKShare `stock_zh_index_daily_em` |")
    lines.append("| Risk-Free Rate | 3.0% per annum, daily = 3% / 252 |")
    lines.append("| Backtest Engine | EasyQuant eqlib — event-driven, T+1 |")
    lines.append("")
    lines.append("> **Disclaimer:** This report is generated by EasyQuant for research purposes only and")
    lines.append("> does not constitute investment advice. Past performance is not indicative of future results.")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report saved: {out_path}")
```

- [ ] **Step 2: Run smoke test**

Run: `python examples/05_reports.py`
Expected: Markdown report generated with grade breakdown and monthly returns tables.

- [ ] **Step 3: Commit**

```bash
git add eqlib/report.py
git commit -m "feat: restructure generate_report_md() with grade breakdown, monthly returns, rolling metrics"
```

---

### Task 9: Upgrade generate_chart() — PNG Dark Theme 4-Panel

**Files:**
- Modify: `eqlib/report.py:334-463` (replace `generate_chart` function)

- [ ] **Step 1: Replace generate_chart()**

Replace the entire `generate_chart` function (lines 334-463) with:

```python
def generate_chart(result, out_path):
    """Generate professional backtest chart (dark theme, 4-panel):
    - Top-left: strategy cumulative return (%) vs benchmark (%)
    - Top-right: radar chart thumbnail (6-dimension grade)
    - Bottom-left: portfolio drawdown (%)
    - Bottom: monthly returns strip
    """
    from eqlib.attribution import analyze_returns, grade_strategy
    from eqlib.brand import DARK_COLORS, apply_matplotlib_dark_theme, apply_matplotlib_brand

    ctx = result["context"]
    trade_log = result["trade_log"]
    recorded = result["recorded_values"]
    benchmark = result.get("benchmark", "000300.XSHG")

    analytics = analyze_returns(result)
    grade_info = grade_strategy(analytics) if analytics else grade_strategy(None)
    c = DARK_COLORS

    pf_entries = sorted(
        recorded.values(), key=lambda x: x.get("date", datetime.date.min)
    ) if isinstance(recorded, dict) else recorded
    pf_records = [r for r in pf_entries if "total_value" in r]
    if not pf_records:
        plt.close()
        return

    initial = ctx.portfolio.starting_cash
    final = ctx.portfolio.total_value
    pnl = final - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

    pf_dates = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in pf_records])
    pf_values = pd.Series([r["total_value"] for r in pf_records], index=pf_dates)
    strat_cum_ret = (pf_values / initial - 1) * 100

    # Benchmark
    bench_cum_ret = None
    try:
        bench_df = fetch_stock_data(benchmark, ctx.start_date, ctx.end_date)
        if not bench_df.empty and "close" in bench_df.columns:
            bench_df = bench_df.sort_index()
            bench_init = bench_df["close"].iloc[0]
            bench_cum_ret = pd.Series(
                (bench_df["close"] / bench_init - 1) * 100,
                index=bench_df.index,
            )
    except Exception:
        pass

    # Figure: 2 rows, 2 columns (top-right for radar)
    fig = plt.figure(figsize=(14, 9), facecolor=c["bg_primary"])
    gs = fig.add_gridspec(3, 2, height_ratios=[3, 1.5, 0.6],
                          hspace=0.15, wspace=0.12,
                          left=0.06, right=0.96, top=0.88, bottom=0.04)
    ax = fig.add_subplot(gs[0, 0])          # cumulative return
    ax_radar = fig.add_subplot(gs[0, 1])    # radar chart
    ax_dd = fig.add_subplot(gs[1, :])       # drawdown (full width)
    ax_monthly = fig.add_subplot(gs[2, :])  # monthly strip (full width)

    # --- Cumulative return ---
    ax.set_facecolor(c["bg_card"])
    ax.plot(pf_dates.to_numpy(), strat_cum_ret.values,
            color=c["chart_strategy"], linewidth=1.8, label="Strategy", zorder=5)
    if bench_cum_ret is not None:
        bench_label = benchmark.replace(".XSHG", "").replace(".XSHE", "")
        ax.plot(bench_cum_ret.index.to_numpy(), bench_cum_ret.values,
                color=c["chart_hs300"], linewidth=1.2, alpha=0.7, label=bench_label, zorder=4)
    ax.axhline(0, color=c["text_dim"], linewidth=0.6, linestyle="--")
    ax.legend(loc="upper left", fontsize=8, facecolor=c["bg_elevated"],
              edgecolor=c["border"], labelcolor=c["text_secondary"])
    ax.set_ylabel("Cumulative Return (%)", fontsize=9, color=c["text_secondary"])
    ax.tick_params(colors=c["text_secondary"], labelsize=7)
    ax.grid(True, alpha=0.15, color=c["border_light"])
    for spine in ax.spines.values():
        spine.set_color(c["border"])
    ax.set_title(
        f"PnL: {pnl:+,.0f} ({pnl_pct:+.2f}%)  |  Trades: {len(trade_log)}",
        fontsize=11, fontweight="bold", color=c["text_primary"],
    )

    # Metrics annotation
    if analytics:
        ann_ret = analytics.get("annual_return", 0)
        sharpe = analytics.get("sharpe_ratio", 0)
        max_dd = analytics.get("max_drawdown", 0)
        ax.text(
            0.98, 0.03,
            f"Ann.Ret {ann_ret:+.1%}  Sharpe {sharpe:.2f}  MaxDD {max_dd:.1%}",
            transform=ax.transAxes, fontsize=8, fontfamily="monospace",
            ha="right", va="bottom", color=c["text_secondary"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor=c["bg_elevated"],
                      edgecolor=c["border"], alpha=0.9),
        )

    # --- Radar chart (simplified bar chart as matplotlib doesn't do radar easily) ---
    ax_radar.set_facecolor(c["bg_card"])
    dims = grade_info.get("dimensions", [])
    if dims:
        dim_names = [d["name"].replace("_", " ").title() for d in dims]
        dim_scores = [d["score"] for d in dims]
        short_names = ["Return", "Risk", "Adj.", "Trade", "Excess", "Stab."]
        bars = ax_radar.barh(short_names[:len(dims)], dim_scores,
                             color=c["accent"], alpha=0.7, height=0.6)
        ax_radar.set_xlim(0, 100)
        ax_radar.tick_params(colors=c["text_secondary"], labelsize=7)
        ax_radar.set_title(f"Grade: {grade_info['overall']} ({grade_info['score']:.0f}/100)",
                          fontsize=10, color=c["text_primary"])
        for spine in ax_radar.spines.values():
            spine.set_color(c["border"])
        ax_radar.grid(True, axis="x", alpha=0.15, color=c["border_light"])

    # --- Drawdown ---
    ax_dd.set_facecolor(c["bg_card"])
    rolling_max = pf_values.cummax()
    dd_pct = (pf_values - rolling_max) / rolling_max * 100
    ax_dd.fill_between(dd_pct.index.to_numpy(), dd_pct.values, 0,
                       color=c["down"], alpha=0.4, zorder=2)
    ax_dd.axhline(0, color=c["text_dim"], linewidth=0.6, linestyle="--")
    ax_dd.set_ylabel("Drawdown (%)", fontsize=9, color=c["text_secondary"])
    ax_dd.tick_params(colors=c["text_secondary"], labelsize=7)
    ax_dd.grid(True, alpha=0.15, color=c["border_light"])
    for spine in ax_dd.spines.values():
        spine.set_color(c["border"])
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    n_months = max(1, len(pf_dates) // 30)
    ax_dd.xaxis.set_major_locator(mdates.MonthLocator(interval=n_months))

    # --- Monthly returns strip ---
    ax_monthly.set_facecolor(c["bg_card"])
    ax_monthly.axis("off")
    if analytics and analytics.get("monthly_returns"):
        mr = analytics["monthly_returns"]
        month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
        x_positions = np.linspace(0.02, 0.98, 12)
        for i, (key, val) in enumerate(sorted(mr.items())):
            month_idx = int(key.split("-")[1]) - 1
            if i >= 12:
                break
            color = c["up"] if val >= 0 else c["down"]
            alpha = min(1.0, abs(val) * 10)
            ax_monthly.text(x_positions[i], 0.5, f"{month_labels[month_idx]}\n{val:+.1%}",
                           ha="center", va="center", fontsize=7,
                           color=color, fontweight="600",
                           bbox=dict(boxstyle="round,pad=0.3",
                                    facecolor=color, alpha=alpha * 0.15,
                                    edgecolor="none"))

    apply_matplotlib_brand(fig)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.2,
                facecolor=c["bg_primary"])
    plt.close()
    print(f"Chart saved: {out_path}")
```

- [ ] **Step 2: Run smoke test**

Run: `python examples/05_reports.py`
Expected: PNG chart saved with dark background, 4 panels.

- [ ] **Step 3: Commit**

```bash
git add eqlib/report.py
git commit -m "feat: upgrade generate_chart() to dark theme 4-panel layout"
```

---

### Task 10: Rewrite HTML Template — Dark Theme + Hero + Tabbed Charts

**Files:**
- Modify: `eqlib/report.py:990-2569` (replace `_HTML_TEMPLATE` string entirely)
- Modify: `eqlib/report.py:692-915` (update `generate_html_report()` to pass new template variables)

This is the largest task. The HTML template is ~1600 lines and must be replaced entirely.

- [ ] **Step 1: Update generate_html_report() to compute new template variables**

In `generate_html_report()` (line 692), after the `metrics = _calc_metrics(result, bench_data)` line (line 742), add:

```python
    # Grade data
    grade_data = metrics.get("grade_data") or _calc_strategy_score(analyze_returns(result))
    grade_overall = grade_data.get("overall", "N/A")
    grade_score = grade_data.get("score", 0)
    grade_summary = grade_data.get("summary_text", "")
    grade_dims_json = json.dumps(grade_data.get("dimensions", []))

    # Monthly returns
    monthly_returns = analytics_mr = {}
    _ar = analyze_returns(result)
    if _ar:
        monthly_returns = _ar.get("monthly_returns", {})
    monthly_returns_json = json.dumps(monthly_returns)

    # Rolling metrics
    rolling_sharpe_json = json.dumps(_ar.get("rolling_sharpe_60d", []) if _ar else [])
    rolling_vol_json = json.dumps(_ar.get("rolling_volatility_60d", []) if _ar else [])

    # Daily returns stats
    daily_stats = _ar.get("daily_returns_stats", {}) if _ar else {}
    daily_stats_json = json.dumps(daily_stats)

    # Drawdown periods
    dd_periods_json = json.dumps(_ar.get("drawdown_periods", []) if _ar else [])
```

Then in the `_HTML_TEMPLATE.format(...)` call (line 841), add these new keyword arguments:

```python
        grade_overall=grade_overall,
        grade_score=f"{grade_score:.0f}",
        grade_summary=html.escape(grade_summary),
        grade_dims_json=grade_dims_json,
        monthly_returns_json=monthly_returns_json,
        rolling_sharpe_json=rolling_sharpe_json,
        rolling_vol_json=rolling_vol_json,
        daily_stats_json=daily_stats_json,
        dd_periods_json=dd_periods_json,
```

- [ ] **Step 2: Replace _HTML_TEMPLATE with dark theme version**

Replace the entire `_HTML_TEMPLATE = """..."""` string (lines 990-2569) with the new dark-theme template. The new template has this structure:

**CSS** (~350 lines): Dark variables, layout, hero, metric cards, charts, tables, modal, responsive.
**HTML body** (~200 lines): Modal → Header → Hero → Core metrics → K-line → Tabbed charts → Drawdown → Daily P&L → Analysis panels → Trade details → Footer.
**JavaScript** (~500 lines): Metric definitions, chart initialization, tab switching, radar SVG, heatmap rendering, histogram canvas, crosshair legend.

The complete new template is provided in the companion file: `docs/superpowers/plans/2026-06-05-html-template.md`. Copy the full content of that file to replace `_HTML_TEMPLATE`.

**Key changes from the old template:**
1. CSS `:root` variables use dark colors (`--bg: #0c1222`, etc.)
2. Hero section with grade letter, radar placeholder, summary text
3. Core metrics row has 4 prominent cards (not 20+ flat cards)
4. Tabbed chart area (Cumulative/Heatmap/Rolling/Distribution) replaces stacked charts
5. Analysis and detail sections use `<details>` for collapsible panels
6. All text colors use `var(--text-primary)` etc.
7. Grade badges with color coding per grade level

- [ ] **Step 3: Create the HTML template companion file**

Since the template is too large to include inline, create `docs/superpowers/plans/2026-06-05-html-template.md` with the complete HTML template string. This file contains:
- Full CSS with dark theme variables
- Full HTML body with all sections
- Full JavaScript with chart init, tabs, radar, heatmap, histogram

The engineer should copy the entire content of this file (between the `"""` delimiters) to replace `_HTML_TEMPLATE` in report.py.

- [ ] **Step 4: Run smoke test**

Run: `python examples/05_reports.py`
Expected: HTML report generated with dark theme. Open the file in a browser to verify.

- [ ] **Step 5: Commit**

```bash
git add eqlib/report.py docs/superpowers/plans/2026-06-05-html-template.md
git commit -m "feat: rewrite HTML report template with dark Bloomberg-style theme"
```

---

### Task 11: Full Regression — All Tests Must Pass

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL tests pass (449+ existing + new grading tests)

- [ ] **Step 2: Run example smoke tests**

Run: `python -m pytest tests/test_examples_smoke.py -v --tb=short`
Expected: All example smoke tests pass

- [ ] **Step 3: Run example 03 (manual backtest)**

Run: `python examples/03_run_backtest.py`
Expected: Backtest completes, metrics printed, no errors

- [ ] **Step 4: Run example 05 (report generation)**

Run: `python examples/05_reports.py`
Expected: All 4 report formats generated successfully

- [ ] **Step 5: Run import sanity check**

Run: `python -c "from eqlib import *; print('eqlib OK')"`
Expected: `eqlib OK`

- [ ] **Step 6: Fix any failures**

If any test fails, diagnose and fix. Do not proceed until ALL tests pass.

- [ ] **Step 7: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve regression in [describe what failed]"
```

---

### Task 12: Verify Examples and Tutorials Still Work

**Files:**
- Potentially modify: `examples/05_reports.py` (already updated in Task 7)
- Potentially modify: other examples that call report functions

- [ ] **Step 1: Run all report-related examples**

```bash
python examples/03_run_backtest.py
python examples/05_reports.py
python examples/09_attribution.py
```
Expected: All complete without error

- [ ] **Step 2: Check that generated reports have correct content**

```bash
# Check JSON has verdict
python -c "
import json
with open('reports/05_report.json') as f:
    r = json.load(f)
assert 'verdict' in r, 'Missing verdict'
assert 'targets' in r, 'Missing targets'
assert 'grade' in r, 'Missing grade'
print(f'Grade: {r[\"verdict\"][\"grade\"]} ({r[\"verdict\"][\"score\"]}/100)')
print(f'Pass: {r[\"verdict\"][\"pass\"]}')
print(f'Targets: {len(r[\"targets\"])}')
print('JSON OK')
"

# Check HTML has dark theme
grep -c "bg_primary\|#0c1222\|DARK" reports/05_report.html

# Check MD has grade breakdown
grep -c "Grade Breakdown" reports/05_report.md
```

- [ ] **Step 3: Run doc build if any docs were changed**

```bash
mkdocs build --strict
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: report enhancement complete — all tests pass, examples verified"
```
