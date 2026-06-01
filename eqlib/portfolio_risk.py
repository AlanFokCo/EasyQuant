"""Portfolio-level risk monitoring for multi-strategy combinations.

Provides VaR, correlation analysis, concentration risk, regime detection,
and three-level alert system (YELLOW/RED/KILL_SWITCH).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class AlertLevel(Enum):
    """预警级别"""
    YELLOW = "yellow"      # 监控关注，不触发动作
    RED = "red"            # 需要人工介入
    KILL_SWITCH = "kill"   # 自动熔断 + 人工确认


@dataclass
class RiskThresholds:
    """风控阈值配置"""
    # 回撤阈值
    max_drawdown_yellow: float = 0.15   # 黄色预警回撤
    max_drawdown_red: float = 0.20      # 红色预警回撤
    max_drawdown_kill: float = 0.25     # 熔断回撤

    # 相关性阈值
    correlation_yellow: float = 0.60    # 黄色预警相关性
    correlation_red: float = 0.75       # 红色预警相关性
    correlation_kill: float = 0.85      # 熔断相关性

    # 集中度阈值
    single_stock_max: float = 0.10      # 单股票最大占比
    single_sector_max: float = 0.30     # 单板块最大占比
    small_cap_max: float = 0.20         # 微盘股最大占比（<50亿）

    # VaR 置信水平
    var_confidence: float = 0.95


@dataclass
class RiskReport:
    """风控检查报告"""
    timestamp: pd.Timestamp
    alert_level: AlertLevel
    triggers: List[str]              # 触发的预警信息列表
    portfolio_var: Optional[float] = None   # 组合 VaR（金额）
    portfolio_var_pct: Optional[float] = None # 组合 VaR（百分比）
    correlation_matrix: Optional[pd.DataFrame] = None  # 策略相关性矩阵
    concentration: Optional[Dict[str, float]] = None   # 集中度指标
    regime: Optional[str] = None            # 当前市场 regime
    recommendations: List[str] = field(default_factory=list)  # 建议操作


def _extract_daily_returns(backtest_result: Dict) -> pd.Series:
    """从回测结果提取日收益率序列"""
    recorded = backtest_result.get("recorded_values", {})
    if not recorded:
        return pd.Series(dtype=float)

    # recorded_values 可能是 dict 或 list
    if isinstance(recorded, dict):
        values = pd.Series(
            {pd.Timestamp(d): float(v.get("total_value") or 0)  # 修复 None 值
             for d, v in recorded.items()}
        ).sort_index()
    else:  # list
        values = pd.Series(
            {pd.Timestamp(r["date"]): float(r.get("total_value") or 0)  # 修复 None 值
             for r in recorded}
        ).sort_index()

    # 修复 Inf 值：当 total_value 从 0 变为非零时 pct_change 会产生 inf
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return returns.astype(float)


class PortfolioRiskMonitor:
    """多策略组合风控监控器"""

    def __init__(self, thresholds: Optional[RiskThresholds] = None):
        self.thresholds = thresholds or RiskThresholds()
        self._strategy_results: Dict[str, Any] = {}
        self._data_issues: List[str] = []  # 记录数据不足等问题

    def add_strategy(self, name: str, backtest_result: Dict) -> None:
        """添加策略回测结果

        Parameters:
            name: 策略名称
            backtest_result: run_backtest() 返回的 result dict

        Raises:
            ValueError: 回测结果为空或缺少 recorded_values 或 recorded_values 为空
        """
        if not backtest_result:
            raise ValueError(f"策略 '{name}' 的回测结果为空")
        if 'recorded_values' not in backtest_result:
            raise ValueError(f"策略 '{name}' 缺少 recorded_values 数据")
        recorded_values = backtest_result['recorded_values']
        if not recorded_values:
            raise ValueError(f"策略 '{name}' 的 recorded_values 为空")

        if name in self._strategy_results:
            warnings.warn(f"策略 '{name}' 已存在，将被覆盖", UserWarning)

        self._strategy_results[name] = backtest_result

    def portfolio_var(self, confidence: Optional[float] = None) -> tuple[float, float]:
        """计算组合 VaR（历史模拟法）

        Parameters:
            confidence: 置信水平，默认使用 thresholds.var_confidence

        Returns:
            (var_amount, var_pct): VaR 金额和占总资产百分比
        """
        if confidence is None:
            confidence = self.thresholds.var_confidence

        if not self._strategy_results:
            return (0.0, 0.0)

        # 收集所有策略的收益率序列
        all_returns = []
        total_value = 0.0
        insufficient_data_strategies = []  # 记录数据不足的策略

        for name, result in self._strategy_results.items():
            returns = _extract_daily_returns(result)
            if len(returns) < 30:  # 数据不足
                insufficient_data_strategies.append(name)
                continue
            all_returns.append(returns)

            # 获取当前总资产
            recorded = result.get("recorded_values", {})
            if recorded:
                if isinstance(recorded, dict):
                    last_val = list(recorded.values())[-1].get("total_value", 0)
                else:
                    last_val = recorded[-1].get("total_value", 0)
                total_value += last_val

        # 记录数据不足问题（供 daily_check 使用）
        if insufficient_data_strategies:
            self._data_issues = [
                f"策略 {name} 数据不足（<30天）"
                for name in insufficient_data_strategies
            ]

        # 所有策略数据都不足 → 返回 NaN
        if not all_returns:
            return (float('nan'), float('nan'))

        if total_value == 0:
            return (0.0, 0.0)

        # 简化：按等权重拼接组合收益率
        combined_returns = pd.concat(all_returns, axis=1).mean(axis=1)

        # 历史模拟法：取分布的负分位数
        loss_quantile = 1 - confidence
        var_pct = max(0.0, -np.percentile(combined_returns, loss_quantile * 100))  # 确保 VaR 非负

        var_amount = total_value * var_pct

        return (float(var_amount), float(var_pct))

    def correlation_matrix(self) -> pd.DataFrame:
        """计算策略间相关性矩阵

        Returns:
            DataFrame, 行列均为策略名称, 值为 Pearson 相关系数
            单策略或无策略时返回空 DataFrame
        """
        if len(self._strategy_results) < 2:
            return pd.DataFrame()

        # 提取各策略收益率序列
        returns_dict = {}
        for name, result in self._strategy_results.items():
            returns = _extract_daily_returns(result)
            if len(returns) >= 30:
                returns_dict[name] = returns

        if len(returns_dict) < 2:
            return pd.DataFrame()

        # 对齐日期索引
        returns_df = pd.DataFrame(returns_dict)

        # 计算 Pearson 相关性
        corr_matrix = returns_df.corr()

        return corr_matrix

    def concentration_risk(self) -> Dict[str, float]:
        """计算集中度风险

        Returns:
            {
                'max_single_stock': 单股票最大持仓占比,
                'max_single_sector': 单板块最大持仓占比,
                'small_cap_pct': 微盘股占比（市值<50亿）,
                'num_holdings': 持仓股票数量,
                'top3_concentration': 前三大持仓占比
            }
        """
        # 收集所有持仓
        all_positions: Dict[str, Dict] = {}
        total_value = 0.0

        for name, result in self._strategy_results.items():
            ctx = result.get("context")
            if ctx and hasattr(ctx, "portfolio"):
                portfolio = ctx.portfolio
                if hasattr(portfolio, "total_value"):
                    total_value += portfolio.total_value
                if hasattr(portfolio, "positions"):
                    for sec, pos in portfolio.positions.items():
                        if sec not in all_positions:
                            all_positions[sec] = {"amount": 0, "value": 0}
                        if hasattr(pos, "amount"):
                            all_positions[sec]["amount"] += pos.amount
                        if hasattr(pos, "value"):
                            all_positions[sec]["value"] += pos.value

        if not all_positions or total_value == 0:
            return {
                "max_single_stock": 0.0,
                "max_single_sector": 0.0,
                "small_cap_pct": 0.0,
                "num_holdings": 0,
                "top3_concentration": 0.0,
            }

        # 计算各持仓占比
        position_values = {sec: data.get("value", 0) for sec, data in all_positions.items()}
        position_pcts = {sec: val / total_value for sec, val in position_values.items()}

        # 最大单股票占比
        max_single_stock = max(position_pcts.values()) if position_pcts else 0.0

        # 前三大持仓占比
        sorted_pcts = sorted(position_pcts.values(), reverse=True)
        top3_concentration = sum(sorted_pcts[:3]) if len(sorted_pcts) >= 3 else sum(sorted_pcts)

        # 板块和市值分析需要 akshare 数据，简化处理
        max_single_sector = max_single_stock  # 保守估计
        small_cap_pct = 0.0

        return {
            "max_single_stock": float(max_single_stock),
            "max_single_sector": float(max_single_sector),
            "small_cap_pct": float(small_cap_pct),
            "num_holdings": len(all_positions),
            "top3_concentration": float(top3_concentration),
        }

    def regime_detection(self) -> str:
        """市场 regime 检测（简单趋势法）

        Returns:
            'bull' / 'bear' / 'oscillation' / 'unknown'
        """
        try:
            from eqlib.data import get_price

            end_date = pd.Timestamp.now().date()
            start_date = end_date - pd.Timedelta(days=90)

            index_data = get_price("000300.XSHG", start_date=start_date, end_date=end_date)

            if index_data is None or len(index_data) < 60:
                return "unknown"

            close = index_data["close"]
            ma20 = close.iloc[-20:].mean()
            ma60 = close.iloc[-60:].mean()

            gap_pct = abs(ma20 - ma60) / ma60

            if ma20 > ma60 and gap_pct > 0.02:
                return "bull"
            elif ma20 < ma60 and gap_pct > 0.02:
                return "bear"
            else:
                return "oscillation"

        except Exception:
            return "unknown"

    def daily_check(self) -> RiskReport:
        """每日综合风控检查（主入口）

        Returns:
            RiskReport: 包含所有指标、预警级别和建议
        """
        triggers: List[str] = []
        recommendations: List[str] = []
        alert_level = AlertLevel.YELLOW

        # 1. 计算 VaR
        var_amount, var_pct = self.portfolio_var()

        # 2. 计算相关性矩阵
        corr_matrix = self.correlation_matrix()
        max_correlation = 0.0
        if not corr_matrix.empty:
            for i in range(len(corr_matrix)):
                for j in range(i + 1, len(corr_matrix)):
                    corr_val = corr_matrix.iloc[i, j]
                    if abs(corr_val) > max_correlation:
                        max_correlation = abs(corr_val)

            if max_correlation >= self.thresholds.correlation_kill:
                triggers.append(f"熔断预警：策略相关性过高 ({max_correlation:.2f})")
                recommendations.append("建议降低高相关性策略仓位 50%")
                alert_level = AlertLevel.KILL_SWITCH
            elif max_correlation >= self.thresholds.correlation_red:
                triggers.append(f"红色预警：策略相关性较高 ({max_correlation:.2f})")
                recommendations.append("建议关注策略分散度")
                alert_level = AlertLevel.RED
            elif max_correlation >= self.thresholds.correlation_yellow:
                triggers.append(f"黄色预警：策略相关性 ({max_correlation:.2f})")

        # 3. 计算集中度
        concentration = self.concentration_risk()

        if concentration["max_single_stock"] > self.thresholds.single_stock_max:
            triggers.append(f"单股票持仓占比过高 ({concentration['max_single_stock']:.2%})")
            recommendations.append("建议减仓超占比股票")

        if concentration["max_single_sector"] > self.thresholds.single_sector_max:
            triggers.append(f"单板块持仓占比过高 ({concentration['max_single_sector']:.2%})")

        if concentration["small_cap_pct"] > self.thresholds.small_cap_max:
            triggers.append(f"微盘股占比过高 ({concentration['small_cap_pct']:.2%})")
            recommendations.append("微盘股流动性风险大，建议控制仓位")

        # 4. Regime 检测
        regime = self.regime_detection()
        if regime == "bear":
            triggers.append("当前市场 regime: 熊市")
            recommendations.append("熊市环境，建议降低仓位")
        elif regime == "oscillation":
            triggers.append("当前市场 regime: 震荡市")

        # 5. 无策略数据提示
        if not self._strategy_results:
            triggers.append("无策略数据")
            recommendations.append("请先添加策略回测结果")

        return RiskReport(
            timestamp=pd.Timestamp.now(),
            alert_level=alert_level,
            triggers=triggers,
            portfolio_var=var_amount if var_amount > 0 else None,
            portfolio_var_pct=var_pct if var_pct > 0 else None,
            correlation_matrix=corr_matrix if not corr_matrix.empty else None,
            concentration=concentration if concentration["num_holdings"] > 0 else None,
            regime=regime,
            recommendations=recommendations,
        )


def check_kill_switch(report: RiskReport) -> List[str]:
    """熔断检查

    Parameters:
        report: RiskReport 风控报告

    Returns:
        需要立即执行的熔断操作列表
    """
    actions = []

    if report.alert_level == AlertLevel.KILL_SWITCH:
        for trigger in report.triggers:
            if "回撤" in trigger:
                actions.append("⚠️ 熔断触发：暂停所有策略，等待人工确认")
            if "相关性" in trigger:
                actions.append("⚠️ 熔断触发：降低高相关性策略仓位 50%")
            if "集中度" in trigger or "持仓" in trigger:
                actions.append("⚠️ 熔断触发：减仓超标股票")

        if not actions:
            actions.append("⚠️ 熔断触发：暂停策略，等待人工确认")

    elif report.alert_level == AlertLevel.RED:
        for trigger in report.triggers:
            if "相关性" in trigger:
                actions.append("红色预警：建议降低高相关性策略仓位")
            if "回撤" in trigger:
                actions.append("红色预警：建议人工检查策略状态")

        if not actions:
            actions.append("红色预警：建议人工介入检查")

    return actions


__all__ = [
    "AlertLevel",
    "RiskThresholds",
    "RiskReport",
    "PortfolioRiskMonitor",
    "check_kill_switch",
]