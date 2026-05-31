"""Portfolio-level risk monitoring for multi-strategy combinations.

Provides VaR, correlation analysis, concentration risk, regime detection,
and three-level alert system (YELLOW/RED/KILL_SWITCH).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

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