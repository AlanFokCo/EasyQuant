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
