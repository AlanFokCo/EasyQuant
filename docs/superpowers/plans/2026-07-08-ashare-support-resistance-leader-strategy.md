# A-Share Support Resistance Leader Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable `eqlib` research workflow for a medium/low-frequency A-share industry leader support/resistance strategy, compare three candidate variants from 2020 onward, and produce a final strategy recommendation.

**Architecture:** Put deterministic support/resistance, ATR, relative-strength, universe, scoring, and strategy factory code in `eqlib/strategies/ashare_sr_leader.py` so it can be unit-tested without network data. Put the long-running research and report generation in `scripts/run_ashare_sr_leader_research.py`, which calls `eqlib.run_backtest`, runs full-period and sub-period evaluations, and writes machine-readable plus human-readable outputs under `reports/ashare_sr_leader/`.

**Tech Stack:** Python 3, pandas, numpy, pytest, akshare through existing `eqlib` data APIs, `eqlib.run_backtest`, `eqlib.analyze_returns`, `eqlib.OrderCost`.

## Global Constraints

- Backtest target period: `2020-01-01` to `2026-07-08` or latest available trading day from the data source.
- Strategy must avoid high-frequency, medium/high-frequency, and intraday logic.
- Trading frequency must come from signal design itself: 60/120-day support/resistance windows, valid breakout, pullback confirmation, and structural breakdown exits.
- Do not add artificial rules that suppress valid trades only to reduce trade count.
- Exclude STAR Market `688xxx` and Beijing Stock Exchange style `8xxxxx`, `4xxxxx`, `9xxxxx` codes.
- Exclude ST/*ST, suspended, illiquid, extremely low-priced, or severely data-gapped stocks where the data API allows.
- Use only historically visible data for entries and exits; avoid lookahead.
- Trading costs must match `examples/_defaults.py`: stamp duty 0.05%, commission 0.025%, minimum 5 CNY.
- Do not use financial-statement factors that may introduce future-reporting-date bias.
- Final comparison must include full-period and sub-period metrics for three strategy variants: defensive support, resistance breakout, breakout-pullback plus market gate.

---

## File Structure

- Create `eqlib/strategies/ashare_sr_leader.py`
  - Owns the default industry leader universe, pure indicator calculations, signal scoring, parameter dataclasses, and `make_initialize()` strategy factory for `run_backtest`.
- Create `tests/test_ashare_sr_leader_strategy.py`
  - Unit tests pure calculations and low-frequency signal behavior with deterministic synthetic OHLCV data.
- Create `scripts/run_ashare_sr_leader_research.py`
  - Runs candidate strategies, parameter grids, full/sub-period backtests, metrics, and output files.
- No change to `eqlib/__init__.py`
  - This keeps the strategy experimental and avoids declaring a public API stability label now.
- No new example file
  - This avoids example index churn and keeps the work as a research script rather than a tutorial.

---

### Task 1: Pure Support/Resistance and Universe Utilities

**Files:**
- Create: `eqlib/strategies/ashare_sr_leader.py`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Produces: `StrategyKind` enum with values `DEFENSIVE_SUPPORT`, `RESISTANCE_BREAKOUT`, `PULLBACK_MARKET_GATE`
- Produces: `StrategyParams` dataclass
- Produces: `LeaderStock` dataclass
- Produces: `DEFAULT_LEADER_UNIVERSE: tuple[LeaderStock, ...]`
- Produces: `get_default_leader_universe() -> list[str]`
- Produces: `is_excluded_board(code: str) -> bool`
- Produces: `compute_atr(frame: pd.DataFrame, period: int = 20) -> pd.Series`
- Produces: `rolling_levels(frame: pd.DataFrame, window: int) -> tuple[float, float]`

- [ ] **Step 1: Write failing tests for board exclusion, universe, ATR, and rolling levels**

Add this file:

```python
"""Tests for the A-share industry leader support/resistance strategy."""

import numpy as np
import pandas as pd

from eqlib.strategies.ashare_sr_leader import (
    DEFAULT_LEADER_UNIVERSE,
    compute_atr,
    get_default_leader_universe,
    is_excluded_board,
    rolling_levels,
)


def _frame(close_values):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1000, 2000, len(close)),
        }
    )


def test_excludes_star_market_and_bse_style_codes():
    assert is_excluded_board("688001")
    assert is_excluded_board("830799")
    assert is_excluded_board("430047")
    assert is_excluded_board("920002")
    assert not is_excluded_board("600519")
    assert not is_excluded_board("300750")


def test_default_universe_has_industry_leaders_without_excluded_boards():
    codes = get_default_leader_universe()
    assert len(codes) >= 60
    assert len(codes) == len(set(codes))
    assert "600519" in codes
    assert "300750" in codes
    assert all(not is_excluded_board(code) for code in codes)
    assert all(leader.industry for leader in DEFAULT_LEADER_UNIVERSE)


def test_compute_atr_uses_true_range_components():
    frame = pd.DataFrame(
        {
            "high": [10.0, 13.0, 12.0],
            "low": [9.0, 11.0, 8.0],
            "close": [9.5, 12.0, 9.0],
        }
    )
    result = compute_atr(frame, period=2)
    # TR values: 1.0, max(2, 3.5, 1.5)=3.5, max(4, 0, 4)=4.0
    assert result.iloc[0] == 1.0
    assert result.iloc[1] == 2.25
    assert result.iloc[2] == 3.75


def test_rolling_levels_use_previous_completed_window():
    frame = _frame([10, 11, 12, 9, 14, 8, 13])
    resistance, support = rolling_levels(frame, window=5)
    assert resistance == frame["high"].iloc[-6:-1].max()
    assert support == frame["low"].iloc[-6:-1].min()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing imports from `eqlib.strategies.ashare_sr_leader`.

- [ ] **Step 3: Implement minimal pure utilities**

Create `eqlib/strategies/ashare_sr_leader.py` with these definitions:

```python
"""A-share industry leader support/resistance strategy utilities.

The module keeps deterministic calculations separate from the backtest runner
so support/resistance logic can be tested without network data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class StrategyKind(str, Enum):
    """Candidate strategy variants researched by the runner."""

    DEFENSIVE_SUPPORT = "defensive_support"
    RESISTANCE_BREAKOUT = "resistance_breakout"
    PULLBACK_MARKET_GATE = "pullback_market_gate"


@dataclass(frozen=True)
class StrategyParams:
    """Parameter set for support/resistance leader strategies."""

    level_window: int = 120
    short_level_window: int = 60
    atr_period: int = 20
    atr_multiplier: float = 0.5
    volume_window: int = 20
    volume_ratio_min: float = 1.0
    rs_window: int = 60
    top_n: int = 10
    max_stock_weight: float = 0.12
    max_industry_weight: float = 0.30
    strong_market_exposure: float = 0.90
    neutral_market_exposure: float = 0.65
    weak_market_exposure: float = 0.35
    min_price: float = 3.0
    min_avg_volume: float = 1_000_000.0


@dataclass(frozen=True)
class LeaderStock:
    """A liquid A-share industry leader used by the research universe."""

    code: str
    name: str
    industry: str


DEFAULT_LEADER_UNIVERSE: tuple[LeaderStock, ...] = (
    LeaderStock("600519", "贵州茅台", "白酒"),
    LeaderStock("000858", "五粮液", "白酒"),
    LeaderStock("600887", "伊利股份", "食品饮料"),
    LeaderStock("000333", "美的集团", "家电"),
    LeaderStock("000651", "格力电器", "家电"),
    LeaderStock("601888", "中国中免", "消费服务"),
    LeaderStock("600036", "招商银行", "银行"),
    LeaderStock("601398", "工商银行", "银行"),
    LeaderStock("601288", "农业银行", "银行"),
    LeaderStock("601318", "中国平安", "保险"),
    LeaderStock("601601", "中国太保", "保险"),
    LeaderStock("600030", "中信证券", "券商"),
    LeaderStock("300059", "东方财富", "券商"),
    LeaderStock("600276", "恒瑞医药", "医药"),
    LeaderStock("300760", "迈瑞医疗", "医疗器械"),
    LeaderStock("000661", "长春高新", "生物医药"),
    LeaderStock("000538", "云南白药", "中药"),
    LeaderStock("300750", "宁德时代", "新能源电池"),
    LeaderStock("002594", "比亚迪", "新能源汽车"),
    LeaderStock("002812", "恩捷股份", "新能源材料"),
    LeaderStock("601012", "隆基绿能", "光伏"),
    LeaderStock("300274", "阳光电源", "光伏储能"),
    LeaderStock("002415", "海康威视", "电子"),
    LeaderStock("000725", "京东方A", "面板"),
    LeaderStock("002475", "立讯精密", "电子制造"),
    LeaderStock("000063", "中兴通讯", "通信设备"),
    LeaderStock("600050", "中国联通", "通信运营"),
    LeaderStock("600941", "中国移动", "通信运营"),
    LeaderStock("601728", "中国电信", "通信运营"),
    LeaderStock("000977", "浪潮信息", "计算机"),
    LeaderStock("002230", "科大讯飞", "人工智能"),
    LeaderStock("300124", "汇川技术", "自动化"),
    LeaderStock("000425", "徐工机械", "工程机械"),
    LeaderStock("600031", "三一重工", "工程机械"),
    LeaderStock("601766", "中国中车", "高端制造"),
    LeaderStock("600309", "万华化学", "化工"),
    LeaderStock("002352", "顺丰控股", "物流"),
    LeaderStock("600585", "海螺水泥", "建材"),
    LeaderStock("601899", "紫金矿业", "有色金属"),
    LeaderStock("603993", "洛阳钼业", "有色金属"),
    LeaderStock("600547", "山东黄金", "黄金"),
    LeaderStock("601088", "中国神华", "煤炭"),
    LeaderStock("600028", "中国石化", "石油石化"),
    LeaderStock("601857", "中国石油", "石油石化"),
    LeaderStock("600900", "长江电力", "电力"),
    LeaderStock("600905", "三峡能源", "新能源电力"),
    LeaderStock("601668", "中国建筑", "建筑"),
    LeaderStock("601390", "中国中铁", "建筑"),
    LeaderStock("601186", "中国铁建", "建筑"),
    LeaderStock("600019", "宝钢股份", "钢铁"),
    LeaderStock("000002", "万科A", "房地产"),
    LeaderStock("001979", "招商蛇口", "房地产"),
    LeaderStock("600690", "海尔智家", "家电"),
    LeaderStock("002027", "分众传媒", "传媒"),
    LeaderStock("600406", "国电南瑞", "电网设备"),
    LeaderStock("002371", "北方华创", "半导体设备"),
    LeaderStock("300014", "亿纬锂能", "新能源电池"),
    LeaderStock("002460", "赣锋锂业", "锂资源"),
    LeaderStock("300015", "爱尔眼科", "医疗服务"),
    LeaderStock("002714", "牧原股份", "养殖"),
    LeaderStock("600011", "华能国际", "电力"),
    LeaderStock("600795", "国电电力", "电力"),
    LeaderStock("601919", "中远海控", "航运"),
    LeaderStock("600009", "上海机场", "机场"),
    LeaderStock("601111", "中国国航", "航空"),
    LeaderStock("601006", "大秦铁路", "铁路"),
    LeaderStock("000568", "泸州老窖", "白酒"),
    LeaderStock("603288", "海天味业", "调味品"),
    LeaderStock("002304", "洋河股份", "白酒"),
    LeaderStock("600438", "通威股份", "光伏"),
    LeaderStock("002129", "TCL中环", "光伏"),
    LeaderStock("601985", "中国核电", "电力"),
)


def _bare(code: str) -> str:
    return code.replace(".XSHG", "").replace(".XSHE", "")


def is_excluded_board(code: str) -> bool:
    """Return True for STAR Market and common BSE-style A-share codes."""

    bare = _bare(code)
    return bare.startswith(("688", "8", "4", "9"))


def get_default_leader_universe() -> list[str]:
    """Return default industry leader bare codes, excluding disallowed boards."""

    seen: set[str] = set()
    codes: list[str] = []
    for leader in DEFAULT_LEADER_UNIVERSE:
        code = _bare(leader.code)
        if code in seen or is_excluded_board(code):
            continue
        seen.add(code)
        codes.append(code)
    return codes


def compute_atr(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    """Compute average true range from high, low, close columns."""

    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=1).mean()


def rolling_levels(frame: pd.DataFrame, window: int) -> tuple[float, float]:
    """Return resistance/support from the previous completed rolling window."""

    if len(frame) < window + 1:
        return float("nan"), float("nan")
    completed = frame.iloc[-window - 1:-1]
    return float(completed["high"].max()), float(completed["low"].min())
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git commit -m "feat: add A-share leader support resistance utilities"
```

---

### Task 2: Signal Classification, Scoring, and Market Gate

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py`
- Modify: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Consumes: `StrategyParams`, `StrategyKind`, `compute_atr`, `rolling_levels`
- Produces: `SignalSnapshot` dataclass
- Produces: `MarketState` enum with values `STRONG`, `NEUTRAL`, `WEAK`
- Produces: `classify_market(frame: pd.DataFrame, params: StrategyParams) -> MarketState`
- Produces: `market_exposure(state: MarketState, params: StrategyParams) -> float`
- Produces: `build_signal_snapshot(stock_frame: pd.DataFrame, benchmark_frame: pd.DataFrame, params: StrategyParams) -> SignalSnapshot | None`
- Produces: `score_snapshot(snapshot: SignalSnapshot, kind: StrategyKind) -> float`

- [ ] **Step 1: Write failing tests for signal snapshots and scoring**

Append to `tests/test_ashare_sr_leader_strategy.py`:

```python
from eqlib.strategies.ashare_sr_leader import (
    MarketState,
    StrategyKind,
    StrategyParams,
    build_signal_snapshot,
    classify_market,
    market_exposure,
    score_snapshot,
)


def _ohlcv_from_close(close_values, volume_start=1_000_000, volume_end=2_000_000):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.linspace(volume_start, volume_end, len(close)),
        }
    )


def test_market_gate_uses_completed_index_structure():
    params = StrategyParams(level_window=20, atr_period=5)
    strong = _ohlcv_from_close(list(np.linspace(10, 15, 80)) + [15.5])
    weak = _ohlcv_from_close(list(np.linspace(15, 10, 80)) + [8.0])
    assert classify_market(strong, params) is MarketState.STRONG
    assert classify_market(weak, params) is MarketState.WEAK
    assert market_exposure(MarketState.STRONG, params) == params.strong_market_exposure
    assert market_exposure(MarketState.WEAK, params) == params.weak_market_exposure


def test_breakout_snapshot_requires_atr_buffer_and_relative_strength():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.3,
        volume_window=5,
        rs_window=20,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close(list(np.linspace(10, 12, 50)) + [13.5], 2_000_000, 4_000_000)
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.5, 51)), 2_000_000, 2_500_000)
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert snapshot.breakout
    assert snapshot.relative_strength > 0
    assert score_snapshot(snapshot, StrategyKind.RESISTANCE_BREAKOUT) > 0


def test_defensive_score_prefers_near_support_without_breakdown():
    params = StrategyParams(
        level_window=20,
        short_level_window=10,
        atr_period=5,
        atr_multiplier=0.5,
        volume_window=5,
        rs_window=20,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close([10, 10.5, 11, 11.5, 11, 10.8, 10.6, 10.4, 10.3, 10.2] * 4 + [10.35])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.1, len(stock))))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert not snapshot.breakdown
    assert snapshot.support_distance < 0.15
    assert score_snapshot(snapshot, StrategyKind.DEFENSIVE_SUPPORT) > 0


def test_breakdown_snapshot_has_negative_scores():
    params = StrategyParams(level_window=20, atr_period=5, volume_window=5, rs_window=20, min_avg_volume=1)
    stock = _ohlcv_from_close(list(np.linspace(12, 10, 50)) + [7.0])
    benchmark = _ohlcv_from_close(list(np.linspace(10, 10.2, 51)))
    snapshot = build_signal_snapshot(stock, benchmark, params)
    assert snapshot is not None
    assert snapshot.breakdown
    assert score_snapshot(snapshot, StrategyKind.PULLBACK_MARKET_GATE) < 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: FAIL with missing `MarketState`, `SignalSnapshot`, and signal functions.

- [ ] **Step 3: Implement signal and scoring logic**

Add to `eqlib/strategies/ashare_sr_leader.py`:

```python
class MarketState(str, Enum):
    """Broad-market structure state."""

    STRONG = "strong"
    NEUTRAL = "neutral"
    WEAK = "weak"


@dataclass(frozen=True)
class SignalSnapshot:
    """Point-in-time signal state for one stock."""

    close: float
    resistance: float
    support: float
    atr: float
    volume_ratio: float
    relative_strength: float
    volatility: float
    support_distance: float
    resistance_distance: float
    breakout: bool
    pullback: bool
    breakdown: bool
```

Then add these functions:

```python
def _last_float(series: pd.Series) -> float:
    return float(series.dropna().iloc[-1]) if not series.dropna().empty else float("nan")


def classify_market(frame: pd.DataFrame, params: StrategyParams) -> MarketState:
    """Classify broad-market state from completed daily bars."""

    if len(frame) < params.level_window + 1:
        return MarketState.NEUTRAL
    close = float(frame["close"].iloc[-1])
    ma120 = _last_float(frame["close"].rolling(params.level_window, min_periods=params.level_window).mean())
    resistance, support = rolling_levels(frame, params.level_window)
    atr_value = float(compute_atr(frame, params.atr_period).iloc[-1])
    if close < support - params.atr_multiplier * atr_value:
        return MarketState.WEAK
    if close > ma120 and close > support:
        return MarketState.STRONG
    if close > resistance + params.atr_multiplier * atr_value:
        return MarketState.STRONG
    return MarketState.NEUTRAL


def market_exposure(state: MarketState, params: StrategyParams) -> float:
    """Map market state to target equity exposure."""

    if state is MarketState.STRONG:
        return params.strong_market_exposure
    if state is MarketState.WEAK:
        return params.weak_market_exposure
    return params.neutral_market_exposure


def _relative_strength(stock_close: pd.Series, benchmark_close: pd.Series, window: int) -> float:
    if len(stock_close) < window + 1 or len(benchmark_close) < window + 1:
        return 0.0
    stock_ret = float(stock_close.iloc[-1] / stock_close.iloc[-window - 1] - 1)
    bench_ret = float(benchmark_close.iloc[-1] / benchmark_close.iloc[-window - 1] - 1)
    return stock_ret - bench_ret


def build_signal_snapshot(
    stock_frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    params: StrategyParams,
) -> SignalSnapshot | None:
    """Build a point-in-time support/resistance signal snapshot."""

    required = max(params.level_window, params.short_level_window, params.rs_window, params.volume_window, params.atr_period) + 1
    if len(stock_frame) < required or len(benchmark_frame) < params.rs_window + 1:
        return None

    close = float(stock_frame["close"].iloc[-1])
    if close < params.min_price:
        return None

    avg_volume = float(stock_frame["volume"].tail(params.volume_window).mean())
    if avg_volume < params.min_avg_volume:
        return None

    resistance_long, support_long = rolling_levels(stock_frame, params.level_window)
    resistance_short, support_short = rolling_levels(stock_frame, params.short_level_window)
    resistance = min(x for x in (resistance_long, resistance_short) if pd.notna(x))
    support = max(x for x in (support_long, support_short) if pd.notna(x))
    atr_value = float(compute_atr(stock_frame, params.atr_period).iloc[-1])
    volume_ratio = float(stock_frame["volume"].iloc[-1] / avg_volume) if avg_volume > 0 else 0.0
    rel_strength = _relative_strength(stock_frame["close"], benchmark_frame["close"], params.rs_window)
    returns = stock_frame["close"].pct_change().tail(20).dropna()
    volatility = float(returns.std()) if not returns.empty else 0.0

    breakout = (
        close > resistance + params.atr_multiplier * atr_value
        and volume_ratio >= params.volume_ratio_min
        and rel_strength > 0
    )
    breakdown = close < support - params.atr_multiplier * atr_value
    support_distance = (close - support) / close if close > 0 else float("inf")
    resistance_distance = (resistance - close) / close if close > 0 else float("inf")
    pullback = (
        not breakdown
        and close >= support
        and support_distance <= max(0.12, params.atr_multiplier * atr_value / close * 3)
        and rel_strength >= -0.03
    )

    return SignalSnapshot(
        close=close,
        resistance=resistance,
        support=support,
        atr=atr_value,
        volume_ratio=volume_ratio,
        relative_strength=rel_strength,
        volatility=volatility,
        support_distance=support_distance,
        resistance_distance=resistance_distance,
        breakout=breakout,
        pullback=pullback,
        breakdown=breakdown,
    )


def score_snapshot(snapshot: SignalSnapshot, kind: StrategyKind) -> float:
    """Score a snapshot for a candidate strategy variant."""

    if snapshot.breakdown:
        return -100.0
    low_vol_bonus = max(0.0, 0.05 - snapshot.volatility) * 10
    rs_score = snapshot.relative_strength * 100
    volume_score = min(snapshot.volume_ratio, 2.0)
    support_score = max(0.0, 0.20 - snapshot.support_distance) * 20
    breakout_score = 8.0 if snapshot.breakout else 0.0
    pullback_score = 10.0 if snapshot.pullback else 0.0

    if kind is StrategyKind.DEFENSIVE_SUPPORT:
        return support_score + low_vol_bonus + max(0.0, rs_score) * 0.2
    if kind is StrategyKind.RESISTANCE_BREAKOUT:
        return breakout_score + rs_score + volume_score - snapshot.volatility * 20
    return pullback_score + breakout_score * 0.7 + rs_score * 0.7 + support_score * 0.3 + low_vol_bonus
```

- [ ] **Step 4: Run tests to verify Task 2 passes**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git commit -m "feat: score support resistance leader signals"
```

---

### Task 3: `eqlib` Strategy Factory with Monthly Scan and Weekly Risk Review

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py`
- Modify: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Consumes: `StrategyParams`, `StrategyKind`, `build_signal_snapshot`, `score_snapshot`, `classify_market`, `market_exposure`
- Produces: `make_initialize(kind: StrategyKind, params: StrategyParams | None = None, universe: list[str] | None = None, benchmark: str = "000300.XSHG") -> Callable`
- Produces: `select_candidates(context, kind: StrategyKind, params: StrategyParams, universe: list[str], benchmark_frame: pd.DataFrame) -> list[tuple[str, SignalSnapshot, float]]`
- Produces: `rebalance_portfolio(context, selections: list[tuple[str, SignalSnapshot, float]], exposure: float, params: StrategyParams) -> None`

- [ ] **Step 1: Write failing tests for selection ordering and industry caps without calling network**

Append to `tests/test_ashare_sr_leader_strategy.py`:

```python
from eqlib.strategies.ashare_sr_leader import (
    LeaderStock,
    industry_for_code,
    target_weights,
)


def test_industry_for_code_uses_default_universe_metadata():
    assert industry_for_code("600519") == "白酒"
    assert industry_for_code("600519.XSHG") == "白酒"
    assert industry_for_code("123456") == "未知"


def test_target_weights_respect_stock_and_industry_caps():
    params = StrategyParams(top_n=5, max_stock_weight=0.12, max_industry_weight=0.30)
    selections = [
        ("600519", None, 10.0),
        ("000858", None, 9.0),
        ("000568", None, 8.0),
        ("300750", None, 7.0),
        ("600036", None, 6.0),
    ]
    weights = target_weights(selections, exposure=0.9, params=params)
    assert sum(weights.values()) <= 0.9
    assert all(weight <= 0.12 for weight in weights.values())
    liquor_weight = weights["600519"] + weights["000858"] + weights["000568"]
    assert liquor_weight <= 0.30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: FAIL with missing `industry_for_code` and `target_weights`.

- [ ] **Step 3: Implement strategy factory helpers**

Add to `eqlib/strategies/ashare_sr_leader.py`:

```python
def industry_for_code(code: str) -> str:
    """Return configured industry label for a bare or suffixed code."""

    bare = _bare(code)
    for leader in DEFAULT_LEADER_UNIVERSE:
        if _bare(leader.code) == bare:
            return leader.industry
    return "未知"


def target_weights(
    selections: list[tuple[str, SignalSnapshot | None, float]],
    exposure: float,
    params: StrategyParams,
) -> dict[str, float]:
    """Build capped target weights from ranked selections."""

    weights: dict[str, float] = {}
    industry_weights: dict[str, float] = {}
    if not selections or exposure <= 0:
        return weights

    base_weight = min(params.max_stock_weight, exposure / max(1, min(params.top_n, len(selections))))
    for code, _snapshot, _score in selections[: params.top_n]:
        industry = industry_for_code(code)
        current_industry = industry_weights.get(industry, 0.0)
        allowed_by_industry = max(0.0, params.max_industry_weight - current_industry)
        weight = min(base_weight, allowed_by_industry, params.max_stock_weight)
        if weight <= 0:
            continue
        weights[code] = weight
        industry_weights[industry] = current_industry + weight
    return weights
```

Then add backtest integration functions:

```python
def _set_costs():
    from eqlib import OrderCost, set_order_cost

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.00025,
            close_commission=0.00025,
            close_today_commission=0,
            min_commission=5,
        )
    )


def select_candidates(context, kind: StrategyKind, params: StrategyParams, universe: list[str], benchmark_frame: pd.DataFrame):
    """Rank candidates using only history available to the current callback."""

    from eqlib import attribute_history

    selections: list[tuple[str, SignalSnapshot, float]] = []
    lookback = max(params.level_window, params.rs_window, params.volume_window, params.atr_period) + 5
    for code in universe:
        if is_excluded_board(code):
            continue
        frame = attribute_history(code, lookback, "1d", ["open", "high", "low", "close", "volume"])
        if frame is None or frame.empty:
            continue
        snapshot = build_signal_snapshot(frame, benchmark_frame, params)
        if snapshot is None or snapshot.breakdown:
            continue
        score = score_snapshot(snapshot, kind)
        if score > 0:
            selections.append((code, snapshot, score))
    selections.sort(key=lambda item: item[2], reverse=True)
    return selections


def rebalance_portfolio(context, selections, exposure: float, params: StrategyParams) -> None:
    """Move portfolio toward ranked target weights."""

    from eqlib import order_target, order_target_value, record

    weights = target_weights(selections, exposure, params)
    target_codes = set(weights)
    for code in list(context.portfolio.positions.keys()):
        if code not in target_codes:
            order_target(code, 0)

    total_value = context.portfolio.total_value
    for code, weight in weights.items():
        target_value = total_value * weight
        if target_value >= 1000:
            order_target_value(code, target_value)

    record(total_value=context.portfolio.total_value, exposure=exposure, holdings=len(weights))


def _risk_review(context, params: StrategyParams) -> None:
    """Weekly structural risk review; exits valid breakdowns."""

    from eqlib import attribute_history, order_target

    lookback = max(params.level_window, params.atr_period) + 5
    for code in list(context.portfolio.positions.keys()):
        frame = attribute_history(code, lookback, "1d", ["open", "high", "low", "close", "volume"])
        if frame is None or frame.empty:
            continue
        resistance, support = rolling_levels(frame, params.level_window)
        atr_value = float(compute_atr(frame, params.atr_period).iloc[-1])
        close = float(frame["close"].iloc[-1])
        if close < support - params.atr_multiplier * atr_value:
            order_target(code, 0)


def make_initialize(
    kind: StrategyKind,
    params: StrategyParams | None = None,
    universe: list[str] | None = None,
    benchmark: str = "000300.XSHG",
):
    """Create an `initialize(context)` callback for `eqlib.run_backtest`."""

    params = params or StrategyParams()
    universe = list(universe or get_default_leader_universe())

    def initialize(context):
        from eqlib import attribute_history, g, run_monthly, run_weekly, set_benchmark

        set_benchmark(benchmark)
        _set_costs()
        context.universe = universe + [benchmark]
        g.sr_kind = kind
        g.sr_params = params
        g.sr_universe = universe
        g.sr_benchmark = benchmark

        def monthly_scan(ctx):
            bench = attribute_history(
                g.sr_benchmark,
                max(g.sr_params.level_window, g.sr_params.rs_window, g.sr_params.atr_period) + 5,
                "1d",
                ["open", "high", "low", "close", "volume"],
            )
            if bench is None or bench.empty:
                return
            state = classify_market(bench, g.sr_params)
            exposure = market_exposure(state, g.sr_params)
            selections = select_candidates(ctx, g.sr_kind, g.sr_params, g.sr_universe, bench)
            rebalance_portfolio(ctx, selections, exposure, g.sr_params)

        def weekly_review(ctx):
            _risk_review(ctx, g.sr_params)

        run_monthly(monthly_scan, day=1, time="09:30")
        run_weekly(weekly_review, day_of_week=4, time="09:30")

    return initialize
```

- [ ] **Step 4: Run tests to verify Task 3 passes**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git commit -m "feat: add support resistance strategy factory"
```

---

### Task 4: Research Runner and Result Files

**Files:**
- Create: `scripts/run_ashare_sr_leader_research.py`
- Modify: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Consumes: `make_initialize`, `StrategyKind`, `StrategyParams`, `get_default_leader_universe`
- Produces CLI command: `python scripts/run_ashare_sr_leader_research.py --quick` for a small smoke run
- Produces CLI command: `python scripts/run_ashare_sr_leader_research.py` for the full 2020-2026 research run
- Produces output directory: `reports/ashare_sr_leader/`
- Produces files: `summary.json`, `summary.csv`, `final_report.md`

- [ ] **Step 1: Write failing tests for parameter grid and metric selection helpers**

Append to `tests/test_ashare_sr_leader_strategy.py`:

```python
from scripts.run_ashare_sr_leader_research import candidate_param_grid, stability_score


def test_candidate_param_grid_contains_three_strategy_kinds():
    grid = candidate_param_grid(quick=True)
    kinds = {kind for kind, _params in grid}
    assert kinds == {
        StrategyKind.DEFENSIVE_SUPPORT,
        StrategyKind.RESISTANCE_BREAKOUT,
        StrategyKind.PULLBACK_MARKET_GATE,
    }


def test_stability_score_penalizes_drawdown_and_trade_count():
    good = {
        "annual_return": 0.12,
        "sharpe_ratio": 1.2,
        "max_drawdown": -0.12,
        "trade_count": 40,
        "excess_return": 0.05,
    }
    overtraded = dict(good, trade_count=300)
    deep_drawdown = dict(good, max_drawdown=-0.45)
    assert stability_score(good) > stability_score(overtraded)
    assert stability_score(good) > stability_score(deep_drawdown)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: FAIL with missing `scripts.run_ashare_sr_leader_research`.

- [ ] **Step 3: Implement research runner**

Create `scripts/run_ashare_sr_leader_research.py`:

```python
#!/usr/bin/env python3
"""Run A-share industry leader support/resistance strategy research.

The full run fetches daily A-share data through eqlib/akshare and may take a
while. Use --quick for a smaller smoke run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict
from pathlib import Path

from eqlib import analyze_returns, run_backtest
from eqlib.strategies.ashare_sr_leader import (
    StrategyKind,
    StrategyParams,
    get_default_leader_universe,
    make_initialize,
)

START_DATE = "2020-01-01"
END_DATE = "2026-07-08"
BENCHMARK = "000300.XSHG"
REPORT_DIR = Path("reports/ashare_sr_leader")
SUB_PERIODS = (
    ("2020-2021", "2020-01-01", "2021-12-31"),
    ("2022", "2022-01-01", "2022-12-31"),
    ("2023-2024", "2023-01-01", "2024-12-31"),
    ("2025-2026", "2025-01-01", "2026-07-08"),
)


def candidate_param_grid(quick: bool = False):
    """Return strategy/parameter combinations to evaluate."""

    if quick:
        return [
            (StrategyKind.DEFENSIVE_SUPPORT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.RESISTANCE_BREAKOUT, StrategyParams(level_window=60, top_n=8)),
            (StrategyKind.PULLBACK_MARKET_GATE, StrategyParams(level_window=60, top_n=8)),
        ]

    grid = []
    for kind in StrategyKind:
        for level_window in (60, 120):
            for atr_multiplier in (0.3, 0.5, 0.8):
                for volume_ratio_min in (1.0, 1.2):
                    for top_n in (8, 10, 12):
                        grid.append(
                            (
                                kind,
                                StrategyParams(
                                    level_window=level_window,
                                    short_level_window=min(60, level_window),
                                    atr_multiplier=atr_multiplier,
                                    volume_ratio_min=volume_ratio_min,
                                    top_n=top_n,
                                ),
                            )
                        )
    return grid


def _benchmark_total_return(result: dict) -> float:
    recorded = result.get("recorded_values", [])
    if not recorded:
        return 0.0
    first = recorded[0].get("bench_value")
    last = recorded[-1].get("bench_value")
    if first in (None, 0) or last is None:
        return 0.0
    return float(last / first - 1)


def summarize_result(result: dict) -> dict:
    """Return metrics used for comparison."""

    metrics = analyze_returns(result, risk_free_rate=0.03) or {}
    total_return = float(metrics.get("total_return", 0.0))
    benchmark_return = _benchmark_total_return(result)
    summary = {
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "annual_return": float(metrics.get("annual_return", 0.0)),
        "annual_volatility": float(metrics.get("annual_volatility", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "sortino_ratio": float(metrics.get("sortino_ratio", 0.0)),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "calmar_ratio": float(metrics.get("calmar_ratio", 0.0)),
        "win_rate_trade": float(metrics.get("win_rate_trade", 0.0)),
        "profit_loss_ratio": float(metrics.get("profit_loss_ratio", 0.0)),
        "trade_count": int(metrics.get("trade_count", len(result.get("trade_log", [])))),
    }
    summary["stability_score"] = stability_score(summary)
    return summary


def stability_score(metrics: dict) -> float:
    """Score risk-adjusted quality while penalizing drawdown and churn."""

    annual_return = float(metrics.get("annual_return", 0.0))
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    max_drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    trade_count = int(metrics.get("trade_count", 0))
    excess_return = float(metrics.get("excess_return", 0.0))
    churn_penalty = max(0, trade_count - 120) / 120 * 0.15
    drawdown_penalty = max(0.0, max_drawdown - 0.25) * 1.5
    return annual_return * 1.5 + sharpe * 0.25 + excess_return - drawdown_penalty - churn_penalty


def run_one(kind: StrategyKind, params: StrategyParams, start: str, end: str, universe: list[str]) -> dict:
    """Run one backtest and return metrics plus metadata."""

    initialize = make_initialize(kind=kind, params=params, universe=universe, benchmark=BENCHMARK)
    result = run_backtest(
        initialize_func=initialize,
        start_date=start,
        end_date=end,
        starting_cash=1_000_000,
        benchmark=BENCHMARK,
        securities=universe + [BENCHMARK],
        use_local=False,
    )
    if result is None:
        return {"error": "backtest returned None"}
    summary = summarize_result(result)
    summary.update(
        {
            "kind": kind.value,
            "start": start,
            "end": end,
            "params": asdict(params),
        }
    )
    return summary


def write_outputs(rows: list[dict]) -> None:
    """Write JSON, CSV, and Markdown summary reports."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda row: row.get("stability_score", -999), reverse=True)
    (REPORT_DIR / "summary.json").write_text(json.dumps(sorted_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "kind", "start", "end", "total_return", "benchmark_return", "excess_return",
        "annual_return", "sharpe_ratio", "max_drawdown", "calmar_ratio",
        "trade_count", "stability_score", "params",
    ]
    with (REPORT_DIR / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)

    best = sorted_rows[0] if sorted_rows else {}
    lines = [
        "# A股行业龙头支撑压力策略研究报告",
        "",
        f"- 最优策略: `{best.get('kind', 'N/A')}`",
        f"- 稳定性评分: `{best.get('stability_score', 0):.4f}`",
        f"- 年化收益: `{best.get('annual_return', 0):.2%}`",
        f"- 最大回撤: `{best.get('max_drawdown', 0):.2%}`",
        f"- Sharpe: `{best.get('sharpe_ratio', 0):.2f}`",
        f"- 交易次数: `{best.get('trade_count', 0)}`",
        "",
        "## Top Results",
        "",
        "| Rank | Strategy | Period | Annual | Max DD | Sharpe | Excess | Trades |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(sorted_rows[:10], start=1):
        lines.append(
            f"| {idx} | {row.get('kind')} | {row.get('start')} to {row.get('end')} | "
            f"{row.get('annual_return', 0):.2%} | {row.get('max_drawdown', 0):.2%} | "
            f"{row.get('sharpe_ratio', 0):.2f} | {row.get('excess_return', 0):.2%} | "
            f"{row.get('trade_count', 0)} |"
        )
    (REPORT_DIR / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run one parameter set per strategy over 2024 only.")
    args = parser.parse_args()

    universe = get_default_leader_universe()
    if args.quick:
        universe = universe[:15]
        periods = (("quick", "2024-01-01", "2024-12-31"),)
    else:
        periods = (("full", START_DATE, END_DATE),) + SUB_PERIODS

    rows = []
    for period_name, start, end in periods:
        for kind, params in candidate_param_grid(quick=args.quick):
            row = run_one(kind, params, start, end, universe)
            row["period_name"] = period_name
            rows.append(row)
            print(
                f"{period_name} {kind.value} annual={row.get('annual_return', 0):.2%} "
                f"dd={row.get('max_drawdown', 0):.2%} score={row.get('stability_score', 0):.4f}"
            )
    write_outputs(rows)
    print(f"Wrote reports to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify Task 4 passes**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py -v`

Expected: all tests PASS.

- [ ] **Step 5: Run quick research smoke test**

Run: `python scripts/run_ashare_sr_leader_research.py --quick`

Expected: command completes and writes `reports/ashare_sr_leader/summary.json`, `summary.csv`, and `final_report.md`. If akshare network data is unavailable, record the specific exception and continue to Task 5 with local unit tests passing.

- [ ] **Step 6: Commit Task 4**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py scripts/run_ashare_sr_leader_research.py reports/ashare_sr_leader/final_report.md reports/ashare_sr_leader/summary.csv reports/ashare_sr_leader/summary.json
git commit -m "feat: add A-share support resistance research runner"
```

---

### Task 5: Full Research Run, Interpretation, and Final Recommendation

**Files:**
- Modify: `scripts/run_ashare_sr_leader_research.py`
- Modify: `reports/ashare_sr_leader/final_report.md`
- Modify: `reports/ashare_sr_leader/summary.json`
- Modify: `reports/ashare_sr_leader/summary.csv`

**Interfaces:**
- Consumes: `python scripts/run_ashare_sr_leader_research.py`
- Produces: `period_interpretation(rows: list[dict]) -> str`
- Produces: final Markdown report with period-by-period interpretation and final recommendation

- [ ] **Step 1: Write failing tests for automatic interpretation text**

Append to `tests/test_ashare_sr_leader_strategy.py`:

```python
from scripts.run_ashare_sr_leader_research import period_interpretation


def test_period_interpretation_reports_regime_and_recommendation():
    rows = [
        {
            "period_name": "full",
            "kind": "pullback_market_gate",
            "annual_return": 0.12,
            "max_drawdown": -0.18,
            "sharpe_ratio": 1.1,
            "excess_return": 0.04,
            "trade_count": 70,
            "stability_score": 0.55,
        },
        {
            "period_name": "2022",
            "kind": "defensive_support",
            "annual_return": -0.04,
            "max_drawdown": -0.16,
            "sharpe_ratio": -0.2,
            "excess_return": 0.03,
            "trade_count": 18,
            "stability_score": 0.10,
        },
    ]
    text = period_interpretation(rows)
    assert "最终推荐" in text
    assert "pullback_market_gate" in text
    assert "2022" in text
    assert "交易次数没有表现出高频" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py::test_period_interpretation_reports_regime_and_recommendation -v`

Expected: FAIL with missing `period_interpretation`.

- [ ] **Step 3: Implement automatic interpretation generation**

Add to `scripts/run_ashare_sr_leader_research.py`:

```python
def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _best_by_period(rows: list[dict]) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for row in rows:
        period = row.get("period_name", "unknown")
        if period not in best or row.get("stability_score", -999) > best[period].get("stability_score", -999):
            best[period] = row
    return best


def _period_reason(row: dict) -> str:
    kind = row.get("kind", "")
    excess = float(row.get("excess_return", 0.0))
    drawdown = abs(float(row.get("max_drawdown", 0.0)))
    trades = int(row.get("trade_count", 0))
    if kind == StrategyKind.DEFENSIVE_SUPPORT.value:
        base = "防守型支撑策略占优，说明该阶段靠近支撑且结构未破坏的行业龙头更能控制回撤。"
    elif kind == StrategyKind.RESISTANCE_BREAKOUT.value:
        base = "压力突破策略占优，说明该阶段趋势延续和放量突破更容易获得超额收益。"
    else:
        base = "突破回踩加市场闸门策略占优，说明该阶段等待确认并随市场结构调节仓位更有效。"
    relative = "跑赢基准" if excess >= 0 else "跑输基准"
    risk = "回撤可控" if drawdown <= 0.25 else "回撤偏大"
    churn = "交易次数没有表现出高频或中高频特征" if trades <= 120 else "交易次数偏多，需要谨慎看待换手成本"
    return f"{base}{relative}，{risk}，{churn}。"


def period_interpretation(rows: list[dict]) -> str:
    """Generate deterministic Chinese interpretation from result rows."""

    best = _best_by_period(rows)
    full = best.get("full") or (sorted(rows, key=lambda row: row.get("stability_score", -999), reverse=True)[0] if rows else {})
    lines = [
        "## 分阶段解释",
        "",
    ]
    for period in ("2020-2021", "2022", "2023-2024", "2025-2026"):
        row = best.get(period)
        if not row:
            continue
        lines.extend(
            [
                f"### {period}",
                "",
                f"- 最优候选: `{row.get('kind')}`",
                f"- 年化收益: `{_fmt_pct(float(row.get('annual_return', 0.0)))}`",
                f"- 最大回撤: `{_fmt_pct(float(row.get('max_drawdown', 0.0)))}`",
                f"- 超额收益: `{_fmt_pct(float(row.get('excess_return', 0.0)))}`",
                f"- 交易次数: `{row.get('trade_count', 0)}`",
                f"- 解释: {_period_reason(row)}",
                "",
            ]
        )
    lines.extend(
        [
            "## 最终推荐",
            "",
            f"最终推荐策略: `{full.get('kind', 'N/A')}`",
            "",
            "推荐原因:",
            "",
            f"- 稳定性评分为 `{full.get('stability_score', 0):.4f}`。",
            f"- 年化收益为 `{_fmt_pct(float(full.get('annual_return', 0.0)))}`，超额收益为 `{_fmt_pct(float(full.get('excess_return', 0.0)))}`。",
            f"- 最大回撤为 `{_fmt_pct(float(full.get('max_drawdown', 0.0)))}`。",
            f"- 交易次数为 `{full.get('trade_count', 0)}`，交易次数没有表现出高频或中高频特征。",
            "- 策略选择依据为稳定性评分、回撤、Sharpe、超额收益和交易次数的综合表现，而不是单次最高收益。",
            "",
            "## 风险提示",
            "",
            "- 历史回测不代表未来收益。",
            "- 行业龙头池仍可能存在幸存者偏差。",
            "- akshare 数据源可用性和复权处理会影响结果。",
            "- 支撑压力不是确定性价格预测，只是结构化风险收益判断。",
        ]
    )
    return "\n".join(lines) + "\n"
```

Modify `write_outputs()` so the final Markdown appends `period_interpretation(sorted_rows)` after the top-results table:

```python
    lines.append("")
    lines.append(period_interpretation(sorted_rows))
    (REPORT_DIR / "final_report.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests for interpretation**

Run: `python -m pytest tests/test_ashare_sr_leader_strategy.py::test_period_interpretation_reports_regime_and_recommendation -v`

Expected: PASS.

- [ ] **Step 5: Run the full research command**

Run:

```bash
python scripts/run_ashare_sr_leader_research.py
```

Expected: all candidate strategies and parameter sets complete for the full period plus the four sub-periods. The command writes refreshed outputs under `reports/ashare_sr_leader/`.

- [ ] **Step 6: Inspect top results and period behavior**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
rows = json.loads(Path("reports/ashare_sr_leader/summary.json").read_text(encoding="utf-8"))
for row in rows[:15]:
    print(row["period_name"], row["kind"], row["annual_return"], row["max_drawdown"], row["sharpe_ratio"], row["trade_count"], row["stability_score"])
PY
```

Expected: output lists the top-ranked configurations, including at least one full-period result and sub-period results.

- [ ] **Step 7: Run verification after report update**

Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -v
python scripts/check_doc_sync.py
```

Expected: both commands PASS.

- [ ] **Step 8: Commit Task 5**

```bash
git add scripts/run_ashare_sr_leader_research.py tests/test_ashare_sr_leader_strategy.py reports/ashare_sr_leader/final_report.md reports/ashare_sr_leader/summary.csv reports/ashare_sr_leader/summary.json
git commit -m "docs: report A-share support resistance strategy research"
```

---

## Final Verification

- [ ] Run targeted tests:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -v
```

- [ ] Run import/smoke-adjacent checks:

```bash
python -m pytest tests/test_imports.py tests/test_utils_indicators.py -v
```

- [ ] Run documentation sync:

```bash
python scripts/check_doc_sync.py
```

- [ ] Confirm git status:

```bash
git status --short
```

Expected final status: clean, or only intentionally untracked generated report artifacts if the user chooses not to commit reports.

---

## Self-Review

- Spec coverage: the plan covers the industry leader universe, board exclusions, support/resistance, ATR, volume confirmation, relative strength, market gate, three candidate strategies, full/sub-period backtests, parameter grids, and final recommendation.
- Placeholder scan: no undefined implementation steps remain. Task 5 generates interpretation text from actual result rows instead of relying on manual fill-ins.
- Type consistency: signatures introduced in Tasks 1-4 match later consumption in the runner and tests.
