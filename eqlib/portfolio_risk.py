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
            {pd.Timestamp(d): float(v.get("total_value", 0))
             for d, v in recorded.items()}
        ).sort_index()
    else:  # list
        values = pd.Series(
            {pd.Timestamp(r["date"]): float(r["total_value"])
             for r in recorded}
        ).sort_index()

    returns = values.pct_change().dropna()
    return returns.astype(float)


class PortfolioRiskMonitor:
    """多策略组合风控监控器"""

    def __init__(self, thresholds: Optional[RiskThresholds] = None):
        self.thresholds = thresholds or RiskThresholds()
        self._strategy_results: Dict[str, Any] = {}

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

    def portfolio_var(self, confidence: float = None) -> tuple[float, float]:
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

        for name, result in self._strategy_results.items():
            returns = _extract_daily_returns(result)
            if len(returns) < 30:  # 数据不足
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

        if not all_returns or total_value == 0:
            return (0.0, 0.0)

        # 简化：按等权重拼接组合收益率
        combined_returns = pd.concat(all_returns, axis=1).mean(axis=1)

        # 历史模拟法：取分布的负分位数
        loss_quantile = 1 - confidence
        var_pct = -np.percentile(combined_returns, loss_quantile * 100)

        var_amount = total_value * var_pct

        return (float(var_amount), float(var_pct))