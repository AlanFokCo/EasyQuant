# A 股行业龙头支撑压力策略稳健化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留当前 `adaptive_composite` 基线行为的前提下，实现双通道选股、波动率与组合回撤风险预算、滚动验证和稳健候选硬门槛。

**Architecture:** 稳健功能作为 `StrategyParams.robust_enabled` 控制的可选路径加入 `ashare_sr_leader.py`；主信号继续使用现有支撑压力逻辑，候补信号、风险状态和稳健权重由新的纯函数实现。研究脚本先筛全周期候选，再做参数邻域和滚动验证；若无人通过硬门槛，确定性回退到当前 A / 71.3 基线。

**Tech Stack:** Python 3、pandas、NumPy、EasyQuant/eqlib 回测 API、pytest、MkDocs。

## Global Constraints

- 全周期年化收益门槛为 12%，最大回撤必须严格小于 20%，评级必须保持 A（评分不低于 70）。
- 2025 压力验证期相对基准落后不得超过 5%；其他滚动验证期不得落后超过 10%。
- 参数邻域中至少 60% 的结果须保持年化收益不低于 10%、最大回撤不超过 22%。
- 所有交易信号只能读取决策时点之前已经完成的 K 线；不得引入未来数据。
- 新功能默认关闭；`robust_enabled=False` 时必须保持当前 `adaptive_composite` 行为。
- 不修改 `grade_strategy`、撮合引擎或通用交易成本；印花税 0.05%、佣金 0.025%、最低佣金 5 元。
- 不增加新依赖，不扩大股票池，不做大规模随机寻优。
- 工作区已有改动全部保留；每次提交前只暂存该任务列出的文件，并检查 `git diff --cached`。
- `docs/**/*.md` 的策略说明和规格更新必须同时维护中文与 `.en.md` 英文版本。

---

## File Map

- Modify: `eqlib/strategies/ashare_sr_leader.py` — 候补信号、风险状态、稳健候选、权重和运行时接入。
- Modify: `scripts/run_ashare_sr_leader_research.py` — 稳健参数网格、结果切片、硬门槛、邻域验证、归因、报告和最终选择。
- Modify: `tests/test_ashare_sr_leader_strategy.py` — 所有策略纯函数、运行时接入、研究选择和报告回归测试。
- Modify: `docs/explanation/ashare-sr-leader-strategy.md` — 中文策略说明和最终研究结果。
- Modify: `docs/explanation/ashare-sr-leader-strategy.en.md` — 英文策略说明和最终研究结果。
- Regenerate: `reports/ashare_sr_leader/summary.json` — 全周期、验证期、门槛和诊断结构化结果。
- Regenerate: `reports/ashare_sr_leader/summary.csv` — 候选指标和门槛列。
- Regenerate: `reports/ashare_sr_leader/final_report.md` — 中文稳健研究结论。
- Regenerate: `reports/ashare_sr_leader/final_report.html` — 中文 HTML 稳健研究结论。
- Regenerate: `reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html` — 最终通过候选或保留基线的原生回测报告。

### Task 1: Add Fallback Signal Domain Primitives

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:24-84,253-388`
- Test: `tests/test_ashare_sr_leader_strategy.py:8-308`

**Interfaces:**
- Produces: `CandidateChannel`, `FallbackSnapshot`, new robustness fields on `StrategyParams`.
- Produces: `build_fallback_snapshot(stock_frame, benchmark_frame, params) -> FallbackSnapshot | None`.
- Produces: `score_fallback_snapshot(snapshot) -> float`.
- Consumes: existing `rolling_levels()`, `_relative_strength()`, `compute_atr()` and OHLCV frames.

- [ ] **Step 1: Write failing tests for defaults and fallback eligibility**

Add these imports and tests to `tests/test_ashare_sr_leader_strategy.py`:

```python
from eqlib.strategies.ashare_sr_leader import (
    CandidateChannel,
    build_fallback_snapshot,
    score_fallback_snapshot,
)


def test_robust_defaults_leave_baseline_disabled():
    params = StrategyParams()

    assert not params.robust_enabled
    assert params.min_primary_candidates == 5
    assert params.fallback_exposure_cap == 0.25
    assert params.fallback_trailing_drawdown == 0.10
    assert params.target_annual_volatility == 0.18


def test_fallback_snapshot_requires_intact_positive_trend():
    params = StrategyParams(
        robust_enabled=True,
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        fallback_trend_window=30,
        fallback_medium_window=15,
        fallback_trend_lookback=5,
        min_avg_volume=1,
    )
    stock = _ohlcv_from_close(list(np.linspace(10, 14, 70)))
    benchmark = _ohlcv_from_close(list(np.linspace(10, 11, 70)))

    snapshot = build_fallback_snapshot(stock, benchmark, params)

    assert snapshot is not None
    assert snapshot.relative_strength > 0
    assert snapshot.medium_trend_change >= 0
    assert snapshot.channel is CandidateChannel.FALLBACK
    assert score_fallback_snapshot(snapshot) > 0


def test_fallback_snapshot_rejects_falling_or_benchmark_lagging_stock():
    params = StrategyParams(
        robust_enabled=True,
        level_window=20,
        short_level_window=10,
        atr_period=5,
        volume_window=5,
        rs_window=20,
        fallback_trend_window=30,
        fallback_medium_window=15,
        fallback_trend_lookback=5,
        min_avg_volume=1,
    )
    falling = _ohlcv_from_close(list(np.linspace(14, 10, 70)))
    lagging = _ohlcv_from_close(list(np.linspace(10, 10.5, 70)))
    benchmark = _ohlcv_from_close(list(np.linspace(10, 12, 70)))

    assert build_fallback_snapshot(falling, benchmark, params) is None
    assert build_fallback_snapshot(lagging, benchmark, params) is None
```

- [ ] **Step 2: Run the tests and verify the new symbols are missing**

Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_defaults or fallback_snapshot" -q
```

Expected: collection fails because `CandidateChannel` and `build_fallback_snapshot` do not exist.

- [ ] **Step 3: Add the fallback types and configuration**

Add the following definitions to `eqlib/strategies/ashare_sr_leader.py` while leaving every existing default unchanged:

```python
class CandidateChannel(str, Enum):
    """Origin of a robust portfolio candidate."""

    PRIMARY = "primary"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class FallbackSnapshot:
    """Trend and liquidity state for a fallback candidate."""

    close: float
    avg_volume: float
    relative_strength: float
    volatility: float
    medium_trend_change: float
    breakdown: bool
    channel: CandidateChannel = CandidateChannel.FALLBACK
```

Append these fields to `StrategyParams`:

```python
    robust_enabled: bool = False
    min_primary_candidates: int = 5
    fallback_exposure_cap: float = 0.25
    fallback_trailing_drawdown: float = 0.10
    fallback_trend_window: int = 120
    fallback_medium_window: int = 60
    fallback_trend_lookback: int = 20
    fallback_min_relative_strength: float = 0.0
    market_volatility_window: int = 20
    target_annual_volatility: float = 0.18
    market_volatility_floor: float = 0.55
    cautious_drawdown: float = 0.08
    defensive_drawdown: float = 0.12
    protect_drawdown: float = 0.16
```

- [ ] **Step 4: Implement fallback snapshot construction and scoring**

Add these functions beside `build_signal_snapshot()`:

```python
def build_fallback_snapshot(
    stock_frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    params: StrategyParams,
) -> FallbackSnapshot | None:
    """Build a trend-qualified fallback snapshot from completed bars."""

    required = max(
        params.level_window,
        params.short_level_window,
        params.rs_window,
        params.volume_window,
        params.atr_period,
        params.fallback_trend_window,
        params.fallback_medium_window + params.fallback_trend_lookback,
    ) + 1
    if len(stock_frame) < required or len(benchmark_frame) < params.rs_window + 1:
        return None

    close_series = stock_frame["close"].astype(float)
    close = float(close_series.iloc[-1])
    if close < params.min_price:
        return None

    avg_volume = float(stock_frame["volume"].tail(params.volume_window).mean())
    if avg_volume < params.min_avg_volume:
        return None

    long_ma = close_series.rolling(params.fallback_trend_window).mean()
    medium_ma = close_series.rolling(params.fallback_medium_window).mean()
    long_value = float(long_ma.iloc[-1])
    medium_now = float(medium_ma.iloc[-1])
    medium_then = float(medium_ma.iloc[-params.fallback_trend_lookback - 1])
    if pd.isna(long_value) or pd.isna(medium_now) or pd.isna(medium_then):
        return None
    if close <= long_value or medium_now < medium_then:
        return None

    relative_strength = _relative_strength(
        close_series,
        benchmark_frame["close"].astype(float),
        params.rs_window,
    )
    if relative_strength < params.fallback_min_relative_strength:
        return None

    _resistance, support = rolling_levels(stock_frame, params.level_window)
    atr_value = float(compute_atr(stock_frame, params.atr_period).iloc[-1])
    breakdown = close < support - params.atr_multiplier * atr_value
    if breakdown:
        return None

    returns = close_series.pct_change().tail(20).dropna()
    volatility = float(returns.std()) if not returns.empty else 0.0
    medium_trend_change = medium_now / medium_then - 1 if medium_then > 0 else 0.0
    return FallbackSnapshot(
        close=close,
        avg_volume=avg_volume,
        relative_strength=relative_strength,
        volatility=volatility,
        medium_trend_change=medium_trend_change,
        breakdown=False,
    )


def score_fallback_snapshot(snapshot: FallbackSnapshot) -> float:
    """Rank fallback candidates by trend, relative strength, and low volatility."""

    trend_score = max(0.0, snapshot.medium_trend_change) * 100
    relative_strength_score = max(0.0, snapshot.relative_strength) * 100
    low_volatility_score = max(0.0, 0.04 - snapshot.volatility) * 50
    return trend_score + relative_strength_score + low_volatility_score
```

- [ ] **Step 5: Run focused and existing signal tests**

Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "snapshot or composite_score or price_filter" -q
```

Expected: all selected tests pass, including the previous primary-signal tests.

- [ ] **Step 6: Commit the fallback primitives**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust fallback signal primitives"
```

### Task 2: Add Volatility Budget and Portfolio Drawdown State Machine

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:24-84,219-250,454-488`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Produces: `PortfolioRiskState`, `PortfolioRiskTracker`.
- Produces: `market_volatility_factor()`, `update_portfolio_risk()`, `drawdown_risk_multiplier()`, `final_risk_budget()`.
- Consumes: `MarketState`, `market_exposure()`, `StrategyParams`.

- [ ] **Step 1: Write failing tests for volatility scaling and risk transitions**

```python
from eqlib.strategies.ashare_sr_leader import (
    PortfolioRiskState,
    PortfolioRiskTracker,
    drawdown_risk_multiplier,
    final_risk_budget,
    market_volatility_factor,
    update_portfolio_risk,
)


def test_market_volatility_factor_is_bounded_and_never_leverages():
    params = StrategyParams(
        market_volatility_window=20,
        target_annual_volatility=0.18,
        market_volatility_floor=0.55,
    )
    quiet = _ohlcv_from_close(list(np.linspace(100, 103, 40)))
    noisy_returns = np.tile([0.04, -0.035], 20)
    noisy_close = 100 * np.cumprod(1 + noisy_returns)
    noisy = _ohlcv_from_close(noisy_close)

    assert market_volatility_factor(quiet, params) == 1.0
    assert 0.55 <= market_volatility_factor(noisy, params) < 1.0
    assert market_volatility_factor(noisy.iloc[:10], params) is None


def test_portfolio_risk_downgrades_immediately_at_each_threshold():
    params = StrategyParams()
    tracker = PortfolioRiskTracker.initial(1_000_000)

    cautious = update_portfolio_risk(
        tracker, 915_000, MarketState.NEUTRAL, params, allow_recovery=False
    )
    defensive = update_portfolio_risk(
        cautious, 875_000, MarketState.NEUTRAL, params, allow_recovery=False
    )
    protect = update_portfolio_risk(
        defensive, 835_000, MarketState.NEUTRAL, params, allow_recovery=False
    )

    assert cautious.state is PortfolioRiskState.CAUTIOUS
    assert defensive.state is PortfolioRiskState.DEFENSIVE
    assert protect.state is PortfolioRiskState.PROTECT
    assert drawdown_risk_multiplier(protect.state) == 0.25


def test_portfolio_risk_recovers_only_one_level_after_half_loss_recovery():
    params = StrategyParams()
    tracker = PortfolioRiskTracker(
        state=PortfolioRiskState.PROTECT,
        high_water=1_000_000,
        trough=830_000,
    )

    blocked = update_portfolio_risk(
        tracker,
        920_000,
        MarketState.WEAK,
        params,
        allow_recovery=True,
    )
    recovered = update_portfolio_risk(
        tracker,
        920_000,
        MarketState.NEUTRAL,
        params,
        allow_recovery=True,
    )

    assert blocked.state is PortfolioRiskState.PROTECT
    assert recovered.state is PortfolioRiskState.DEFENSIVE
```

- [ ] **Step 2: Run the tests and verify missing risk symbols**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "market_volatility_factor or portfolio_risk" -q
```

Expected: collection fails on the new imports.

- [ ] **Step 3: Implement immutable risk state and transition helpers**

Add `IntEnum` to imports and add the following code:

```python
from enum import Enum, IntEnum

from eqlib.constants import TRADING_DAYS_PER_YEAR


class PortfolioRiskState(IntEnum):
    """Ordered portfolio drawdown states from least to most defensive."""

    NORMAL = 0
    CAUTIOUS = 1
    DEFENSIVE = 2
    PROTECT = 3


@dataclass(frozen=True)
class PortfolioRiskTracker:
    """High-water and trough state for one drawdown episode."""

    state: PortfolioRiskState
    high_water: float
    trough: float

    @classmethod
    def initial(cls, total_value: float) -> "PortfolioRiskTracker":
        return cls(PortfolioRiskState.NORMAL, total_value, total_value)


def _risk_state_for_drawdown(
    drawdown: float,
    params: StrategyParams,
) -> PortfolioRiskState:
    if drawdown >= params.protect_drawdown:
        return PortfolioRiskState.PROTECT
    if drawdown >= params.defensive_drawdown:
        return PortfolioRiskState.DEFENSIVE
    if drawdown >= params.cautious_drawdown:
        return PortfolioRiskState.CAUTIOUS
    return PortfolioRiskState.NORMAL


def update_portfolio_risk(
    tracker: PortfolioRiskTracker,
    total_value: float,
    market_state: MarketState,
    params: StrategyParams,
    allow_recovery: bool,
    data_complete: bool = True,
) -> PortfolioRiskTracker:
    """Downgrade immediately and recover at most one state per review."""

    if total_value <= 0:
        return tracker
    high_water = max(tracker.high_water, total_value)
    trough = min(tracker.trough, total_value)
    drawdown = max(0.0, 1 - total_value / high_water) if high_water > 0 else 0.0
    threshold_state = _risk_state_for_drawdown(drawdown, params)
    if threshold_state > tracker.state:
        return PortfolioRiskTracker(threshold_state, high_water, min(trough, total_value))

    loss = high_water - trough
    recovery_ratio = (total_value - trough) / loss if loss > 0 else 1.0
    can_recover = (
        allow_recovery
        and data_complete
        and market_state is not MarketState.WEAK
        and recovery_ratio >= 0.5
        and threshold_state < tracker.state
    )
    state = PortfolioRiskState(tracker.state - 1) if can_recover else tracker.state
    if state is PortfolioRiskState.NORMAL and total_value >= high_water:
        trough = total_value
    return PortfolioRiskTracker(state, high_water, trough)
```

- [ ] **Step 4: Implement volatility and final budget functions**

```python
def market_volatility_factor(
    benchmark_frame: pd.DataFrame,
    params: StrategyParams,
) -> float | None:
    """Scale risk down when completed benchmark returns exceed target volatility."""

    close = benchmark_frame.get("close")
    if close is None or len(close) < params.market_volatility_window + 1:
        return None
    returns = close.astype(float).pct_change().dropna().tail(params.market_volatility_window)
    if len(returns) < params.market_volatility_window:
        return None
    realized = float(returns.std()) * (TRADING_DAYS_PER_YEAR ** 0.5)
    if realized <= 0:
        return 1.0
    return max(
        params.market_volatility_floor,
        min(1.0, params.target_annual_volatility / realized),
    )


def drawdown_risk_multiplier(state: PortfolioRiskState) -> float:
    """Map a portfolio risk state to its exposure multiplier."""

    return {
        PortfolioRiskState.NORMAL: 1.0,
        PortfolioRiskState.CAUTIOUS: 0.75,
        PortfolioRiskState.DEFENSIVE: 0.50,
        PortfolioRiskState.PROTECT: 0.25,
    }[state]


def final_risk_budget(
    market_state: MarketState,
    volatility_factor: float,
    risk_state: PortfolioRiskState,
    params: StrategyParams,
) -> float:
    """Return the final unlevered equity exposure budget."""

    return max(
        0.0,
        min(
            1.0,
            market_exposure(market_state, params)
            * volatility_factor
            * drawdown_risk_multiplier(risk_state),
        ),
    )
```

- [ ] **Step 5: Add a final-budget assertion and rerun risk tests**

Append to the volatility test:

```python
    budget = final_risk_budget(
        MarketState.STRONG,
        volatility_factor=0.80,
        risk_state=PortfolioRiskState.DEFENSIVE,
        params=StrategyParams(strong_market_exposure=0.90),
    )
    assert budget == 0.36
```

Run:

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "volatility_factor or portfolio_risk or final_risk_budget" -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the risk primitives**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add portfolio risk budget state machine"
```

### Task 3: Add Robust Candidate Composition and Volatility Weights

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:391-451`
- Test: `tests/test_ashare_sr_leader_strategy.py:366-429`

**Interfaces:**
- Produces: `RobustCandidate`.
- Produces: `combine_robust_candidates(primary, fallback, market_state, risk_state, params) -> list[RobustCandidate]`.
- Produces: `robust_target_weights(candidates, exposure, params) -> dict[str, float]`.
- Consumes: `CandidateChannel`, `PortfolioRiskState`, `industry_for_code()`.

- [ ] **Step 1: Write failing tests for primary priority and capped inverse-volatility weights**

```python
from eqlib.strategies.ashare_sr_leader import (
    RobustCandidate,
    combine_robust_candidates,
    robust_target_weights,
)


def _robust_candidate(
    code: str,
    channel: CandidateChannel,
    score: float,
    volatility: float,
) -> RobustCandidate:
    return RobustCandidate(
        code=code,
        channel=channel,
        score=score,
        volatility=volatility,
        close=10.0,
        avg_volume=1_000_000.0,
    )


def test_robust_candidates_use_fallback_only_when_primary_is_short():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=2, top_n=3)
    primary = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.03),
    ]
    fallback = [_robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.01)]

    enough = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )
    short = combine_robust_candidates(
        primary[:1], fallback, MarketState.NEUTRAL, PortfolioRiskState.NORMAL, params
    )

    assert all(item.channel is CandidateChannel.PRIMARY for item in enough)
    assert [item.channel for item in short] == [
        CandidateChannel.PRIMARY,
        CandidateChannel.FALLBACK,
    ]


def test_fallback_is_disabled_in_weak_or_defensive_state():
    params = StrategyParams(robust_enabled=True, min_primary_candidates=2, top_n=3)
    primary = [_robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02)]
    fallback = [_robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.01)]

    weak = combine_robust_candidates(
        primary, fallback, MarketState.WEAK, PortfolioRiskState.NORMAL, params
    )
    defensive = combine_robust_candidates(
        primary, fallback, MarketState.NEUTRAL, PortfolioRiskState.DEFENSIVE, params
    )

    assert weak == primary
    assert defensive == primary


def test_robust_weights_prioritize_primary_and_cap_fallback_and_industry():
    params = StrategyParams(
        robust_enabled=True,
        top_n=4,
        max_stock_weight=0.30,
        max_industry_weight=0.35,
        fallback_exposure_cap=0.20,
    )
    candidates = [
        _robust_candidate("600519", CandidateChannel.PRIMARY, 10.0, 0.02),
        _robust_candidate("300750", CandidateChannel.PRIMARY, 9.0, 0.04),
        _robust_candidate("000858", CandidateChannel.FALLBACK, 8.0, 0.01),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 7.0, 0.02),
    ]

    weights = robust_target_weights(candidates, exposure=0.70, params=params)

    fallback_weight = weights["000858"] + weights["600036"]
    assert fallback_weight <= 0.20
    assert weights["600519"] > weights["300750"]
    assert weights["600519"] + weights["000858"] <= 0.35
    assert sum(weights.values()) <= 0.70
```

- [ ] **Step 2: Run tests and verify robust composition is missing**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_candidates or robust_weights or fallback_is_disabled" -q
```

Expected: collection fails on `RobustCandidate`.

- [ ] **Step 3: Implement candidate composition**

```python
@dataclass(frozen=True)
class RobustCandidate:
    """Normalized candidate used by robust portfolio construction."""

    code: str
    channel: CandidateChannel
    score: float
    volatility: float
    close: float
    avg_volume: float


def combine_robust_candidates(
    primary: list[RobustCandidate],
    fallback: list[RobustCandidate],
    market_state: MarketState,
    risk_state: PortfolioRiskState,
    params: StrategyParams,
) -> list[RobustCandidate]:
    """Keep primary candidates first and add fallback only when allowed."""

    primary_ranked = sorted(primary, key=lambda item: item.score, reverse=True)
    if len(primary_ranked) >= params.min_primary_candidates:
        return primary_ranked[: params.top_n]
    if market_state is MarketState.WEAK or risk_state >= PortfolioRiskState.DEFENSIVE:
        return primary_ranked[: params.top_n]

    chosen = list(primary_ranked[: params.top_n])
    chosen_codes = {item.code for item in chosen}
    for item in sorted(fallback, key=lambda candidate: candidate.score, reverse=True):
        if item.code in chosen_codes or len(chosen) >= params.top_n:
            continue
        chosen.append(item)
        chosen_codes.add(item.code)
    return chosen
```

- [ ] **Step 4: Implement inverse-volatility channel allocation**

```python
def _allocate_robust_channel(
    candidates: list[RobustCandidate],
    budget: float,
    params: StrategyParams,
    weights: dict[str, float],
    industry_weights: dict[str, float],
) -> None:
    if not candidates or budget <= 0:
        return
    inverse = [1 / max(candidate.volatility, 1e-6) for candidate in candidates]
    inverse_total = sum(inverse)
    for candidate, inverse_value in zip(candidates, inverse):
        requested = budget * inverse_value / inverse_total
        industry = industry_for_code(candidate.code)
        industry_room = max(
            0.0,
            params.max_industry_weight - industry_weights.get(industry, 0.0),
        )
        weight = min(requested, params.max_stock_weight, industry_room)
        if weight <= 0:
            continue
        weights[candidate.code] = weight
        industry_weights[industry] = industry_weights.get(industry, 0.0) + weight


def robust_target_weights(
    candidates: list[RobustCandidate],
    exposure: float,
    params: StrategyParams,
) -> dict[str, float]:
    """Allocate primary first, then a capped fallback sleeve without redistribution."""

    selected = candidates[: params.top_n]
    primary = [item for item in selected if item.channel is CandidateChannel.PRIMARY]
    fallback = [item for item in selected if item.channel is CandidateChannel.FALLBACK]
    weights: dict[str, float] = {}
    industry_weights: dict[str, float] = {}
    _allocate_robust_channel(primary, exposure, params, weights, industry_weights)
    remaining = max(0.0, exposure - sum(weights.values()))
    fallback_budget = min(params.fallback_exposure_cap, remaining)
    _allocate_robust_channel(
        fallback,
        fallback_budget,
        params,
        weights,
        industry_weights,
    )
    return weights
```

- [ ] **Step 5: Run focused and legacy weight tests**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "robust_candidates or robust_weights or target_weights or industry" -q
```

Expected: all selected tests pass and legacy `target_weights()` behavior remains unchanged.

- [ ] **Step 6: Commit robust portfolio construction**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust channel portfolio weights"
```

### Task 4: Integrate Robust Selection, Runtime Risk, and Order Diagnostics

**Files:**
- Modify: `eqlib/strategies/ashare_sr_leader.py:535-705`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Produces: `select_fallback_candidates()`, `select_robust_candidates()`, `risk_data_complete()`, `reduce_portfolio_to_budget()`.
- Produces context diagnostics: `sr_order_channels`, `sr_code_channels`, `sr_risk_events`, `sr_risk_tracker`.
- Consumes: Tasks 1-3 interfaces and existing eqlib order/scheduling APIs.

- [ ] **Step 1: Write failing tests for cross-sectional volatility filtering and exposure reduction**

```python
from types import SimpleNamespace

from eqlib.strategies.ashare_sr_leader import (
    filter_fallback_by_volatility,
    reduce_portfolio_to_budget,
    risk_data_complete,
)


def test_fallback_filter_keeps_only_candidates_at_or_below_median_volatility():
    candidates = [
        _robust_candidate("600519", CandidateChannel.FALLBACK, 10.0, 0.01),
        _robust_candidate("300750", CandidateChannel.FALLBACK, 9.0, 0.02),
        _robust_candidate("600036", CandidateChannel.FALLBACK, 8.0, 0.04),
    ]

    filtered = filter_fallback_by_volatility(candidates)

    assert [item.code for item in filtered] == ["600519", "300750"]


def test_reduce_portfolio_to_budget_only_queues_smaller_targets(monkeypatch):
    queued = []
    monkeypatch.setattr(
        "eqlib.order_target_value",
        lambda code, value: queued.append((code, value)) or None,
    )
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            total_value=1_000_000,
            positions={
                "600519": SimpleNamespace(total_value=300_000),
                "600036": SimpleNamespace(total_value=200_000),
            },
        ),
        sr_order_channels={},
        sr_code_channels={
            "600519": CandidateChannel.PRIMARY.value,
            "600036": CandidateChannel.FALLBACK.value,
        },
    )

    reduce_portfolio_to_budget(context, exposure_budget=0.25)

    assert queued == [("600519", 150_000), ("600036", 100_000)]


def test_missing_benchmark_or_volatility_data_blocks_risk_increase():
    assert not risk_data_complete(pd.DataFrame(), None)
    assert not risk_data_complete(_ohlcv_from_close([10, 11]), None)
    assert risk_data_complete(_ohlcv_from_close([10, 11]), 0.80)
```

- [ ] **Step 2: Run tests and confirm runtime helpers are missing**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "fallback_filter or reduce_portfolio" -q
```

Expected: collection fails on the new helper imports.

- [ ] **Step 3: Implement fallback selection and normalized robust candidates**

Add these helpers. `select_fallback_candidates()` should fetch the same completed OHLCV fields as `select_candidates()` and skip excluded codes and current primary codes.

```python
def filter_fallback_by_volatility(
    candidates: list[RobustCandidate],
) -> list[RobustCandidate]:
    """Keep fallback candidates no more volatile than the cross-sectional median."""

    if not candidates:
        return []
    median = float(pd.Series([item.volatility for item in candidates]).median())
    return [item for item in candidates if item.volatility <= median]


def risk_data_complete(
    benchmark_frame: pd.DataFrame,
    volatility_factor: float | None,
) -> bool:
    """Return whether a callback may increase portfolio risk."""

    return not benchmark_frame.empty and volatility_factor is not None


def _primary_candidates(
    selections: list[tuple[str, SignalSnapshot, float]],
) -> list[RobustCandidate]:
    return [
        RobustCandidate(
            code=code,
            channel=CandidateChannel.PRIMARY,
            score=score,
            volatility=snapshot.volatility,
            close=snapshot.close,
            avg_volume=snapshot.avg_volume,
        )
        for code, snapshot, score in selections
    ]


def select_fallback_candidates(
    context,
    params: StrategyParams,
    universe: list[str],
    benchmark_frame: pd.DataFrame,
    excluded_codes: set[str],
) -> list[RobustCandidate]:
    from eqlib import attribute_history

    lookback = max(
        params.level_window,
        params.short_level_window,
        params.rs_window,
        params.volume_window,
        params.atr_period,
        params.fallback_trend_window,
        params.fallback_medium_window + params.fallback_trend_lookback,
    ) + 5
    candidates: list[RobustCandidate] = []
    for code in universe:
        if code in excluded_codes or is_excluded_board(code):
            continue
        frame = attribute_history(
            code,
            lookback,
            "1d",
            ["open", "high", "low", "close", "volume"],
        )
        if frame is None or frame.empty:
            continue
        snapshot = build_fallback_snapshot(frame, benchmark_frame, params)
        if snapshot is None:
            continue
        candidates.append(
            RobustCandidate(
                code=code,
                channel=CandidateChannel.FALLBACK,
                score=score_fallback_snapshot(snapshot),
                volatility=snapshot.volatility,
                close=snapshot.close,
                avg_volume=snapshot.avg_volume,
            )
        )
    return sorted(
        filter_fallback_by_volatility(candidates),
        key=lambda item: item.score,
        reverse=True,
    )
```

- [ ] **Step 4: Implement risk-reducing proportional orders and order tagging**

```python
def _tag_order(context, order, code: str, channel: CandidateChannel) -> None:
    if order is None:
        return
    context.sr_order_channels[str(order.order_id)] = channel.value
    context.sr_code_channels.setdefault(code, channel.value)


def reduce_portfolio_to_budget(context, exposure_budget: float) -> None:
    """Reduce positions proportionally; never increase exposure."""

    from eqlib import order_target_value

    total_value = float(context.portfolio.total_value)
    invested = sum(
        float(position.total_value)
        for position in context.portfolio.positions.values()
    )
    if total_value <= 0 or invested <= total_value * exposure_budget:
        return
    ratio = total_value * exposure_budget / invested
    for code, position in context.portfolio.positions.items():
        target = float(position.total_value) * ratio
        order = order_target_value(code, target)
        channel = CandidateChannel(
            context.sr_code_channels.get(code, CandidateChannel.PRIMARY.value)
        )
        _tag_order(context, order, code, channel)
```

- [ ] **Step 5: Add robust rebalance and channel-specific exits**

Implement `rebalance_robust_portfolio()` beside the legacy rebalance. It must call `robust_target_weights()`, tag every queued order, preserve an existing position's channel, and use the existing liquidity cap for increases. Update `_risk_review()` so fallback holdings use `fallback_trailing_drawdown` while primary holdings retain `max_position_drawdown`.

The channel stop choice must be exactly:

```python
channel = CandidateChannel(
    getattr(context, "sr_code_channels", {}).get(
        code,
        CandidateChannel.PRIMARY.value,
    )
)
stop_pct = (
    params.fallback_trailing_drawdown
    if channel is CandidateChannel.FALLBACK
    else params.max_position_drawdown
)
if should_exit_trailing_drawdown(
    frame,
    stop_pct=stop_pct,
    window=params.short_level_window,
):
    order = order_target(code, 0)
    _tag_order(context, order, code, channel)
```

- [ ] **Step 6: Integrate the robust branch into `make_initialize()`**

Initialize persistent diagnostics only when robust mode is enabled:

```python
        if g.sr_params.robust_enabled:
            context.sr_order_channels = {}
            context.sr_code_channels = {}
            context.sr_risk_events = []
            context.sr_risk_tracker = PortfolioRiskTracker.initial(
                context.portfolio.total_value
            )
```

In monthly robust mode, fetch enough benchmark history for the volatility window, update risk without recovery, return without increasing risk when benchmark/volatility data are missing, reduce only in `PROTECT`, and otherwise select and rebalance robust candidates. In weekly robust mode, update risk with `allow_recovery=True`, append an event when the state changes, run exits first, then call `reduce_portfolio_to_budget()`.

The state-event shape must be deterministic:

```python
{
    "date": context.current_dt.date().isoformat(),
    "from": previous.state.name.lower(),
    "to": updated.state.name.lower(),
    "drawdown": round(
        1 - context.portfolio.total_value / updated.high_water,
        6,
    ),
}
```

Keep the existing monthly and weekly callback bodies unchanged when `robust_enabled` is false.

- [ ] **Step 7: Run the full strategy unit test file**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -q
```

Expected: all tests pass; no network access is needed for these tests.

- [ ] **Step 8: Commit runtime integration**

```bash
git add eqlib/strategies/ashare_sr_leader.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: integrate robust A-share risk controls"
```

### Task 5: Add Robust Research Gates, Neighborhood Checks, and Rolling Validation

**Files:**
- Modify: `scripts/run_ashare_sr_leader_research.py:10-340,869-1080`
- Test: `tests/test_ashare_sr_leader_strategy.py:431-790`

**Interfaces:**
- Produces: `BASELINE_ADAPTIVE_PARAMS`, `VALIDATION_WINDOWS`, `robust_seed_param_grid()`, `neighbor_param_sets()`.
- Produces: `slice_backtest_result()`, `full_gate_failures()`, `validation_gate_failures()`, `neighbor_pass_rate()`, `robust_rank_key()`.
- Consumes: `run_one_result()`, `summarize_result()` and Task 4 strategy runtime.

- [ ] **Step 1: Write failing gate and result-slicing tests**

```python
from scripts.run_ashare_sr_leader_research import (
    BASELINE_ADAPTIVE_PARAMS,
    full_gate_failures,
    neighbor_param_sets,
    neighbor_pass_rate,
    robust_rank_key,
    slice_backtest_result,
    validation_gate_failures,
)


def test_full_gate_requires_return_drawdown_and_a_grade():
    passing = {"annual_return": 0.12, "max_drawdown": -0.199, "grade_score": 70.0}

    assert full_gate_failures(passing) == []
    assert "annual_return_below_12pct" in full_gate_failures(
        dict(passing, annual_return=0.119)
    )
    assert "max_drawdown_not_below_20pct" in full_gate_failures(
        dict(passing, max_drawdown=-0.20)
    )
    assert "grade_below_a" in full_gate_failures(dict(passing, grade_score=69.9))


def test_validation_gate_applies_tighter_2025_limit():
    rows = {
        "2023": {"excess_return": -0.09},
        "2024": {"excess_return": 0.01},
        "2025": {"excess_return": -0.051},
    }

    assert validation_gate_failures(rows) == ["2025_excess_below_minus_5pct"]


def test_neighbor_pass_rate_uses_10pct_return_and_22pct_drawdown():
    neighbors = [
        {"annual_return": 0.11, "max_drawdown": -0.20},
        {"annual_return": 0.10, "max_drawdown": -0.22},
        {"annual_return": 0.09, "max_drawdown": -0.18},
        {"annual_return": 0.12, "max_drawdown": -0.23},
        {"annual_return": 0.13, "max_drawdown": -0.19},
    ]

    assert neighbor_pass_rate(neighbors) == 0.6


def test_slice_backtest_result_rebases_validation_context():
    result = {
        "context": SimpleNamespace(
            portfolio=SimpleNamespace(starting_cash=1_000_000, total_value=1_200_000)
        ),
        "trade_log": [
            {"date": "2022-12-30", "type": "BUY"},
            {"date": "2023-06-01", "type": "SELL"},
        ],
        "recorded_values": [
            {"date": "2022-12-30", "total_value": 1_000_000},
            {"date": "2023-01-03", "total_value": 1_050_000},
            {"date": "2023-12-29", "total_value": 1_200_000},
        ],
        "benchmark": "000300.XSHG",
        "benchmark_values": [
            {"date": "2023-01-03", "value": 100.0},
            {"date": "2023-12-29", "value": 110.0},
        ],
        "ohlcv_data": {},
    }

    sliced = slice_backtest_result(result, "2023-01-01", "2023-12-31")

    assert sliced is not None
    assert sliced["context"].portfolio.starting_cash == 1_050_000
    assert sliced["context"].portfolio.total_value == 1_200_000
    assert len(sliced["trade_log"]) == 1
```

- [ ] **Step 2: Run tests and verify research helpers are missing**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "full_gate or validation_gate or neighbor_pass or slice_backtest" -q
```

Expected: collection fails on new research imports.

- [ ] **Step 3: Define the exact baseline, validation windows, and compact seed grid**

Import `replace` and `SimpleNamespace`, then define:

```python
from dataclasses import asdict, replace
from types import SimpleNamespace


BASELINE_ADAPTIVE_PARAMS = StrategyParams(
    level_window=100,
    short_level_window=50,
    atr_multiplier=0.45,
    volume_ratio_min=0.9,
    top_n=10,
    max_stock_weight=0.10,
    max_industry_weight=0.25,
    strong_market_exposure=0.95,
    neutral_market_exposure=0.68,
    weak_market_exposure=0.25,
    min_relative_strength=-0.015,
    max_support_distance=0.11,
    rebalance_threshold=0.05,
    liquidity_volume_pct=0.04,
)

VALIDATION_WINDOWS = (
    ("2023", "2020-01-01", "2023-12-31", "2023-01-01", "2023-12-31"),
    ("2024", "2021-01-01", "2024-12-31", "2024-01-01", "2024-12-31"),
    ("2025", "2022-01-01", "2025-12-31", "2025-01-01", "2025-12-31"),
)


def robust_seed_param_grid() -> list[StrategyParams]:
    center = replace(BASELINE_ADAPTIVE_PARAMS, robust_enabled=True)
    return [
        center,
        replace(center, min_primary_candidates=4),
        replace(center, min_primary_candidates=6),
        replace(center, fallback_exposure_cap=0.20),
        replace(center, fallback_exposure_cap=0.30),
        replace(center, fallback_trailing_drawdown=0.08),
        replace(center, target_annual_volatility=0.16),
        replace(center, target_annual_volatility=0.20),
        replace(
            center,
            cautious_drawdown=0.07,
            defensive_drawdown=0.11,
            protect_drawdown=0.15,
        ),
        replace(
            center,
            cautious_drawdown=0.09,
            defensive_drawdown=0.13,
            protect_drawdown=0.17,
        ),
    ]
```

`candidate_param_grid(quick=False)` must retain the exact baseline and append robust seeds as `StrategyKind.ADAPTIVE_COMPOSITE` candidates. Quick mode adds only the center robust seed.

- [ ] **Step 4: Implement deterministic neighbor generation and gates**

```python
def neighbor_param_sets(params: StrategyParams) -> list[StrategyParams]:
    variants = [
        replace(params, min_primary_candidates=value) for value in (4, 5, 6)
    ]
    variants.extend(
        replace(params, fallback_exposure_cap=value) for value in (0.20, 0.25, 0.30)
    )
    variants.extend(
        replace(params, fallback_trailing_drawdown=value) for value in (0.08, 0.10)
    )
    variants.extend(
        replace(params, target_annual_volatility=value) for value in (0.16, 0.18, 0.20)
    )
    variants.extend(
        [
            replace(
                params,
                cautious_drawdown=0.07,
                defensive_drawdown=0.11,
                protect_drawdown=0.15,
            ),
            replace(
                params,
                cautious_drawdown=0.09,
                defensive_drawdown=0.13,
                protect_drawdown=0.17,
            ),
        ]
    )
    return list(dict.fromkeys(item for item in variants if item != params))


def full_gate_failures(row: dict) -> list[str]:
    failures: list[str] = []
    if float(row.get("annual_return", 0.0)) < 0.12:
        failures.append("annual_return_below_12pct")
    if abs(float(row.get("max_drawdown", 0.0))) >= 0.20:
        failures.append("max_drawdown_not_below_20pct")
    if float(row.get("grade_score", 0.0)) < 70.0:
        failures.append("grade_below_a")
    return failures


def validation_gate_failures(rows: dict[str, dict]) -> list[str]:
    failures: list[str] = []
    for period, row in rows.items():
        excess = float(row.get("excess_return", 0.0))
        if period == "2025" and excess < -0.05:
            failures.append("2025_excess_below_minus_5pct")
        elif period != "2025" and excess < -0.10:
            failures.append(f"{period}_excess_below_minus_10pct")
    return failures


def neighbor_pass_rate(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    passed = sum(
        float(row.get("annual_return", 0.0)) >= 0.10
        and abs(float(row.get("max_drawdown", 0.0))) <= 0.22
        for row in rows
    )
    return round(passed / len(rows), 6)


def robust_rank_key(row: dict) -> tuple[float, float, float, float, float, float]:
    return (
        float(row.get("neighbor_pass_rate", 0.0)),
        float(row.get("worst_validation_excess", -999.0)),
        float(row.get("sharpe_ratio", -999.0)),
        -abs(float(row.get("max_drawdown", -999.0))),
        float(row.get("monthly_win_rate", 0.0)),
        float(row.get("annual_return", -999.0)),
    )
```

Extend `summarize_result()` with the monthly win rate used by this key:

```python
    monthly_returns = metrics.get("monthly_returns", {}) or {}
    summary["monthly_win_rate"] = (
        sum(value > 0 for value in monthly_returns.values()) / len(monthly_returns)
        if monthly_returns
        else 0.0
    )
```

- [ ] **Step 5: Implement validation result slicing**

```python
def slice_backtest_result(
    result: dict,
    start: str,
    end: str,
) -> dict | None:
    recorded = [
        row
        for row in result.get("recorded_values", [])
        if start <= _date_key(row.get("date")) <= end
    ]
    if len(recorded) < 2:
        return None
    context = SimpleNamespace(
        portfolio=SimpleNamespace(
            starting_cash=float(recorded[0]["total_value"]),
            total_value=float(recorded[-1]["total_value"]),
        )
    )
    trades = [
        trade
        for trade in result.get("trade_log", [])
        if start <= _date_key(trade.get("date")) <= end
    ]
    benchmark_values = [
        row
        for row in result.get("benchmark_values", [])
        if start <= _date_key(row.get("date")) <= end
    ]
    return {
        "context": context,
        "trade_log": trades,
        "recorded_values": recorded,
        "benchmark": result.get("benchmark", BENCHMARK),
        "benchmark_values": benchmark_values,
        "ohlcv_data": result.get("ohlcv_data", {}),
    }
```

- [ ] **Step 6: Refactor `main()` into staged robust research**

Add a dictionary cache keyed by `(kind, params, start, end)` around `run_one_result()`. Run all seed candidates on the full period, apply `full_gate_failures()`, and take at most the top three robust pre-gate passers by Sharpe, drawdown, and annual return. For those finalists:

1. Run every `neighbor_param_sets()` candidate over the full period and set `neighbor_pass_rate`.
2. Run each `VALIDATION_WINDOWS` formation range, slice to its validation year, summarize it, and store rows under `validation`.
3. Set `worst_validation_excess`, `gate_failures`, and `robust_gate_pass`.
4. Select the maximum `robust_rank_key()` only from `robust_gate_pass=True` rows.
5. If none pass, select the exact `BASELINE_ADAPTIVE_PARAMS` row and set `selection_reason="baseline_retained_no_robust_candidate"`.

The final selection code must use this explicit shape:

```python
passing = [
    item for item in full_candidates if item[0].get("robust_gate_pass") is True
]
if passing:
    best_row, best_kind, best_params = max(
        passing,
        key=lambda item: robust_rank_key(item[0]),
    )
    best_row["selection_reason"] = "robust_candidate_passed_all_gates"
else:
    best_row, best_kind, best_params = next(
        item
        for item in full_candidates
        if item[1] is StrategyKind.ADAPTIVE_COMPOSITE
        and item[2] == BASELINE_ADAPTIVE_PARAMS
    )
    best_row["selection_reason"] = "baseline_retained_no_robust_candidate"
```

`gate_failures` must combine all three checks and include
`neighbor_pass_rate_below_60pct` whenever `neighbor_pass_rate < 0.60`:

```python
gate_failures = full_gate_failures(row)
gate_failures.extend(validation_gate_failures(validation_rows))
if float(row.get("neighbor_pass_rate", 0.0)) < 0.60:
    gate_failures.append("neighbor_pass_rate_below_60pct")
row["gate_failures"] = gate_failures
row["robust_gate_pass"] = not gate_failures
```

Mark exactly one full-period row with `selected=True`; every other row gets
`selected=False`. `write_outputs()` must sort the selected full-period row first
before applying diagnostic ranking, so `summary.json[0]` and the report headline
always describe the actual selected strategy.

- [ ] **Step 7: Run research-selection tests**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "gate or neighbor or slice_backtest or best_full_candidate or candidate_param_grid" -q
```

Expected: all selected tests pass, including deterministic baseline fallback.

- [ ] **Step 8: Commit staged robust research**

```bash
git add scripts/run_ashare_sr_leader_research.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: add robust strategy validation gates"
```

### Task 6: Add Channel Attribution, Risk Diagnostics, and Report Sections

**Files:**
- Modify: `scripts/run_ashare_sr_leader_research.py:313-866,921-1001`
- Test: `tests/test_ashare_sr_leader_strategy.py:776-948`

**Interfaces:**
- Produces: `channel_diagnostics(result) -> dict`, `risk_state_diagnostics(result) -> dict`.
- Extends summary rows with gate, validation, neighborhood, risk-state, and channel fields.
- Consumes: `context.sr_order_channels`, `context.sr_risk_events`, `trade_log`, `ohlcv_data`, and `recorded_values`.

- [ ] **Step 1: Write failing diagnostic and report tests**

```python
from scripts.run_ashare_sr_leader_research import (
    channel_diagnostics,
    risk_state_diagnostics,
)


def test_channel_diagnostics_attributes_next_day_returns_by_order_channel():
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    result = {
        "context": SimpleNamespace(
            sr_order_channels={"1": "primary", "2": "fallback"}
        ),
        "trade_log": [
            {
                "date": "2025-01-02",
                "type": "BUY",
                "security": "600519",
                "amount": 100,
                "order_id": 1,
            },
            {
                "date": "2025-01-02",
                "type": "BUY",
                "security": "600036",
                "amount": 100,
                "order_id": 2,
            },
        ],
        "recorded_values": [
            {"date": "2025-01-02", "total_value": 10_000},
            {"date": "2025-01-03", "total_value": 10_100},
        ],
        "ohlcv_data": {
            "600519": pd.DataFrame({"close": [10.0, 11.0]}, index=dates),
            "600036": pd.DataFrame({"close": [10.0, 9.0]}, index=dates),
        },
    }

    diagnostics = channel_diagnostics(result)

    assert diagnostics["primary_trade_count"] == 1
    assert diagnostics["fallback_trade_count"] == 1
    assert diagnostics["primary_average_holdings"] == 1.0
    assert diagnostics["fallback_average_holdings"] == 1.0
    assert diagnostics["primary_return_contribution"] == 0.01
    assert diagnostics["fallback_return_contribution"] == -0.01


def test_risk_state_diagnostics_counts_state_duration_and_transitions():
    result = {
        "context": SimpleNamespace(
            sr_risk_events=[
                {"date": "2025-01-03", "from": "normal", "to": "cautious"},
                {"date": "2025-01-06", "from": "cautious", "to": "normal"},
            ]
        ),
        "recorded_values": [
            {"date": "2025-01-02", "total_value": 100},
            {"date": "2025-01-03", "total_value": 95},
            {"date": "2025-01-06", "total_value": 98},
        ],
    }

    diagnostics = risk_state_diagnostics(result)

    assert diagnostics["risk_state_days"] == {"normal": 2, "cautious": 1}
    assert diagnostics["risk_state_trigger_count"] == 1
    assert diagnostics["risk_state_recovery_count"] == 1
```

Extend the HTML report test with:

```python
    assert "稳健门槛" in html
    assert "滚动验证" in html
    assert "风险状态" in html
    assert "主/候补通道" in html
```

- [ ] **Step 2: Run tests and confirm diagnostics are missing**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "channel_diagnostics or risk_state_diagnostics or render_html_report" -q
```

Expected: collection fails on diagnostic imports.

- [ ] **Step 3: Implement order-channel attribution**

Implement `channel_diagnostics()` by reconstructing channel holdings from filled trades. For each recorded date, calculate contribution using the previous close's channel weights and the current close return before applying that date's fills for the next holding period. Use `result["context"].sr_order_channels` to map `order_id` to `primary` or `fallback`.

The returned structure must always contain numeric defaults:

```python
{
    "primary_trade_count": 0,
    "fallback_trade_count": 0,
    "primary_average_exposure": 0.0,
    "fallback_average_exposure": 0.0,
    "primary_average_holdings": 0.0,
    "fallback_average_holdings": 0.0,
    "primary_return_contribution": 0.0,
    "fallback_return_contribution": 0.0,
}
```

Use arithmetic daily contribution, rounded to six decimals. Missing close data skips only that security/date contribution and does not abort the report.

- [ ] **Step 4: Implement risk-state duration diagnostics**

`risk_state_diagnostics()` starts in `normal`, applies events at their recorded date, counts each recorded trading date in the resulting state, counts transitions away from `normal` as triggers, and counts transitions to a lower `PortfolioRiskState` numeric level as recoveries. Return:

```python
{
    "risk_state_days": state_days,
    "risk_state_trigger_count": trigger_count,
    "risk_state_recovery_count": recovery_count,
}
```

- [ ] **Step 5: Attach diagnostics and gate data to summary rows**

Update `run_one()` and the full-period branch in `main()` so each raw result contributes:

```python
summary.update(channel_diagnostics(result))
summary.update(risk_state_diagnostics(result))
summary.setdefault("gate_failures", [])
summary.setdefault("robust_gate_pass", False)
summary.setdefault("neighbor_pass_rate", 0.0)
summary.setdefault("worst_validation_excess", 0.0)
summary.setdefault("validation", {})
```

Add scalar diagnostic fields to CSV. Keep nested `validation`, `risk_state_days`, and `gate_failures` in JSON and render them in Markdown/HTML instead of flattening them into CSV.

- [ ] **Step 6: Add deterministic Markdown and HTML sections**

Add five sections after the full-period ranking:

1. `稳健门槛` — pass/fail and exact failure codes per robust finalist.
2. `滚动验证` — 2023, 2024, and 2025 annual return, excess return, drawdown, and grade.
3. `风险状态` — days by state, trigger count, recovery count.
4. `主/候补通道` — trades, average exposure, and return contribution.
5. `基线与稳健候选对比` — annual return, drawdown, Sharpe, grade, and every hard-gate outcome side by side.

When no robust candidate passes, both reports must include this exact sentence:

```text
本轮没有找到通过全部稳健门槛的新候选，继续保留当前 A / 71.3 基线。
```

- [ ] **Step 7: Run all report and research tests**

```bash
python -m pytest tests/test_ashare_sr_leader_strategy.py -k "diagnostics or report or write_outputs or audit or period_interpretation" -q
```

Expected: all selected tests pass and HTML escaping tests still pass.

- [ ] **Step 8: Commit diagnostics and reports**

```bash
git add scripts/run_ashare_sr_leader_research.py tests/test_ashare_sr_leader_strategy.py
git diff --cached --check
git commit -m "feat: report robust strategy validation"
```

### Task 7: Run Research, Regenerate Reports, and Update Bilingual Explanation

**Files:**
- Modify: `docs/explanation/ashare-sr-leader-strategy.md`
- Modify: `docs/explanation/ashare-sr-leader-strategy.en.md`
- Regenerate: `reports/ashare_sr_leader/summary.json`
- Regenerate: `reports/ashare_sr_leader/summary.csv`
- Regenerate: `reports/ashare_sr_leader/final_report.md`
- Regenerate: `reports/ashare_sr_leader/final_report.html`
- Regenerate: `reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html`
- Test: `tests/test_ashare_sr_leader_strategy.py`

**Interfaces:**
- Consumes: completed robust strategy and research runner.
- Produces: reproducible report artifacts and synchronized user documentation.

- [ ] **Step 1: Run a quick research smoke test**

```bash
MPLCONFIGDIR=/private/tmp/matplotlib-cache python scripts/run_ashare_sr_leader_research.py --quick
```

Expected: exit code 0, at least one baseline and one robust candidate are evaluated, and all report formats are written.

- [ ] **Step 2: Run the full 2020-2025 research**

```bash
MPLCONFIGDIR=/private/tmp/matplotlib-cache python - <<'PY'
from eqlib.logger import log

log.set_level("ERROR")

import scripts.run_ashare_sr_leader_research as research

raise SystemExit(research.main())
PY
```

Expected: exit code 0. The output either selects a candidate that passes every hard gate or explicitly retains `BASELINE_ADAPTIVE_PARAMS`.

- [ ] **Step 3: Verify generated result invariants**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("reports/ashare_sr_leader/summary.json")
rows = json.loads(path.read_text(encoding="utf-8"))
full = [row for row in rows if row.get("period_name") == "full"]
assert full
selected = full[0]
reason = selected.get("selection_reason")
assert reason in {
    "robust_candidate_passed_all_gates",
    "baseline_retained_no_robust_candidate",
}
if reason == "robust_candidate_passed_all_gates":
    assert selected["annual_return"] >= 0.12
    assert abs(selected["max_drawdown"]) < 0.20
    assert selected["grade_score"] >= 70.0
    assert selected["neighbor_pass_rate"] >= 0.60
else:
    assert selected["kind"] == "adaptive_composite"
print(reason)
PY
```

Expected: assertions pass and the printed reason matches the report conclusion.

- [ ] **Step 4: Update both explanation documents from actual results**

Correct stale statements that name `pullback_market_gate` as the 2020-2025 winner. Add matching Chinese and English sections covering:

- Current A / 71.3 `adaptive_composite` baseline and its exact parameters.
- Primary and fallback channel eligibility.
- 8% / 12% / 16% portfolio risk states and 1.00 / 0.75 / 0.50 / 0.25 multipliers.
- 20-day benchmark volatility scaling with 16% / 18% / 20% research targets and a 0.55 floor.
- Hard gates, rolling validation, neighborhood stability, and honest baseline fallback.
- The actual final research outcome and generated report path.

Do not claim that 2025 is untouched out-of-sample data; call it a pressure or stress-validation period.

- [ ] **Step 5: Run documentation synchronization and focused tests**

```bash
python scripts/check_doc_sync.py
python -m pytest tests/test_ashare_sr_leader_strategy.py -q
```

Expected: documentation checks pass and the full strategy test file passes.

- [ ] **Step 6: Commit generated reports and bilingual explanation**

```bash
git add docs/explanation/ashare-sr-leader-strategy.md docs/explanation/ashare-sr-leader-strategy.en.md reports/ashare_sr_leader/summary.json reports/ashare_sr_leader/summary.csv reports/ashare_sr_leader/final_report.md reports/ashare_sr_leader/final_report.html reports/ashare_sr_leader/eqlib_best_backtest_2020_2025.html
git diff --cached --check
git commit -m "docs: publish robust A-share strategy research"
```

### Task 8: Complete Repository Verification

**Files:**
- Verify only; modify the smallest relevant file if a new failure is found.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: final evidence that tests, examples, docs, and generated reports are coherent.

- [ ] **Step 1: Run focused data and strategy regression tests**

```bash
python -m pytest tests/test_data_diagnostics.py tests/test_data_utils.py tests/test_ashare_sr_leader_strategy.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the complete test suite**

```bash
python -m pytest tests/ -q
```

Expected: all tests pass. Existing warnings may remain, but no new warning should originate from the robust strategy files.

- [ ] **Step 3: Run example smoke tests explicitly**

```bash
python -m pytest tests/test_examples_smoke.py -q
```

Expected: all example smoke tests pass.

- [ ] **Step 4: Verify bilingual docs and build MkDocs**

```bash
python scripts/check_doc_sync.py
mkdocs build --strict
```

Expected: both commands pass. If strict mode fails only because of pre-existing Material, navigation, or git-revision warnings, save the exact warnings, run `mkdocs build`, and report the strict-mode limitation without hiding it.

- [ ] **Step 5: Inspect the final diff and report selection**

```bash
git status --short
git diff --check
git log -8 --oneline
```

Expected: no whitespace errors, the task commits are visible, and unrelated pre-existing worktree changes remain untouched.

- [ ] **Step 6: Close verification without an empty commit**

Verification itself creates no commit. If a defect is found, reopen the task that owns the failing behavior, apply its exact staging and test sequence, commit there, and restart Task 8 from Step 1.
