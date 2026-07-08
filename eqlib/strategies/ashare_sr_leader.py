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


class MarketState(str, Enum):
    """Broad-market structure state."""

    STRONG = "strong"
    NEUTRAL = "neutral"
    WEAK = "weak"


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


def _last_float(series: pd.Series) -> float:
    values = series.dropna()
    return float(values.iloc[-1]) if not values.empty else float("nan")


def classify_market(frame: pd.DataFrame, params: StrategyParams) -> MarketState:
    """Classify broad-market state from completed daily bars."""

    if len(frame) < params.level_window + 1:
        return MarketState.NEUTRAL

    close = float(frame["close"].iloc[-1])
    ma = frame["close"].rolling(
        params.level_window,
        min_periods=params.level_window,
    ).mean()
    ma_value = _last_float(ma)
    resistance, support = rolling_levels(frame, params.level_window)
    atr_value = float(compute_atr(frame, params.atr_period).iloc[-1])

    if close < support - params.atr_multiplier * atr_value:
        return MarketState.WEAK
    if close > resistance + params.atr_multiplier * atr_value:
        return MarketState.STRONG
    if pd.notna(ma_value) and close > ma_value and close > support:
        return MarketState.STRONG
    return MarketState.NEUTRAL


def market_exposure(state: MarketState, params: StrategyParams) -> float:
    """Map market state to target equity exposure."""

    if state is MarketState.STRONG:
        return params.strong_market_exposure
    if state is MarketState.WEAK:
        return params.weak_market_exposure
    return params.neutral_market_exposure


def _relative_strength(
    stock_close: pd.Series,
    benchmark_close: pd.Series,
    window: int,
) -> float:
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

    required = (
        max(
            params.level_window,
            params.rs_window,
            params.volume_window,
            params.atr_period,
        )
        + 1
    )
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
    resistance_candidates = [
        value for value in (resistance_long, resistance_short) if pd.notna(value)
    ]
    support_candidates = [
        value for value in (support_long, support_short) if pd.notna(value)
    ]
    if not resistance_candidates or not support_candidates:
        return None

    resistance = min(resistance_candidates)
    support = max(support_candidates)
    atr_value = float(compute_atr(stock_frame, params.atr_period).iloc[-1])
    volume_ratio = float(stock_frame["volume"].iloc[-1] / avg_volume) if avg_volume > 0 else 0.0
    rel_strength = _relative_strength(
        stock_frame["close"],
        benchmark_frame["close"],
        params.rs_window,
    )
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
    return (
        pullback_score
        + breakout_score * 0.7
        + rs_score * 0.7
        + support_score * 0.3
        + low_vol_bonus
    )
