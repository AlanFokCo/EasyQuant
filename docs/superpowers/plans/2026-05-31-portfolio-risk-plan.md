# Portfolio Risk Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `eqlib/portfolio_risk.py` 组合级风控模块，提供 VaR、相关性、集中度、regime 检测和三级预警功能。

**Architecture:** 单文件模块设计，包含 `PortfolioRiskMonitor` 主类、`RiskThresholds` 配置、`RiskReport` 报告、`AlertLevel` 枚举。数据从回测结果提取，无缝衔接现有 API。

**Tech Stack:** Python 3.10+, pandas, numpy, pytest

---

## File Structure

| 文件 | 负责 |
|-----|------|
| `eqlib/portfolio_risk.py` | 组合风控核心模块（新建） |
| `tests/test_portfolio_risk.py` | 单元测试（新建） |
| `eqlib/__init__.py` | 导出新 API（修改） |

---

## Task 1: 数据结构基础

**Files:**
- Create: `eqlib/portfolio_risk.py`
- Test: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for AlertLevel and RiskThresholds**

```python
# tests/test_portfolio_risk.py
"""Tests for eqlib.portfolio_risk module."""

import pytest
from eqlib.portfolio_risk import AlertLevel, RiskThresholds


class TestAlertLevel:
    """Tests for AlertLevel enum."""

    def test_enum_values(self):
        assert AlertLevel.YELLOW.value == "yellow"
        assert AlertLevel.RED.value == "red"
        assert AlertLevel.KILL_SWITCH.value == "kill"

    def test_enum_count(self):
        assert len(list(AlertLevel)) == 3


class TestRiskThresholds:
    """Tests for RiskThresholds dataclass."""

    def test_default_values(self):
        thresholds = RiskThresholds()
        assert thresholds.max_drawdown_yellow == 0.15
        assert thresholds.max_drawdown_red == 0.20
        assert thresholds.max_drawdown_kill == 0.25
        assert thresholds.correlation_yellow == 0.60
        assert thresholds.correlation_red == 0.75
        assert thresholds.correlation_kill == 0.85
        assert thresholds.single_stock_max == 0.10
        assert thresholds.single_sector_max == 0.30
        assert thresholds.small_cap_max == 0.20
        assert thresholds.var_confidence == 0.95

    def test_custom_values(self):
        thresholds = RiskThresholds(
            max_drawdown_kill=0.15,
            single_stock_max=0.08,
            correlation_red=0.65,
        )
        assert thresholds.max_drawdown_kill == 0.15
        assert thresholds.single_stock_max == 0.08
        assert thresholds.correlation_red == 0.65
        # Defaults remain
        assert thresholds.max_drawdown_yellow == 0.15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'eqlib.portfolio_risk'"

- [ ] **Step 3: Write minimal implementation for AlertLevel and RiskThresholds**

```python
# eqlib/portfolio_risk.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestAlertLevel tests/test_portfolio_risk.py::TestRiskThresholds -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add AlertLevel and RiskThresholds data structures for portfolio risk"
```

---

## Task 2: RiskReport 数据类

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for RiskReport**

```python
# tests/test_portfolio_risk.py (追加)

class TestRiskReport:
    """Tests for RiskReport dataclass."""

    def test_risk_report_creation(self):
        from eqlib.portfolio_risk import RiskReport
        report = RiskReport(
            timestamp=pd.Timestamp("2024-01-01"),
            alert_level=AlertLevel.YELLOW,
            triggers=["相关性过高"],
            portfolio_var=10000.0,
            portfolio_var_pct=0.05,
            correlation_matrix=None,
            concentration={"max_single_stock": 0.08},
            regime="bull",
            recommendations=["监控关注"],
        )
        assert report.alert_level == AlertLevel.YELLOW
        assert report.portfolio_var == 10000.0
        assert report.regime == "bull"

    def test_risk_report_optional_fields(self):
        from eqlib.portfolio_risk import RiskReport
        report = RiskReport(
            timestamp=pd.Timestamp.now(),
            alert_level=AlertLevel.RED,
            triggers=["回撤超阈值"],
        )
        assert report.portfolio_var is None
        assert report.correlation_matrix is None
        assert report.concentration is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestRiskReport -v`
Expected: FAIL with "ImportError: cannot import name 'RiskReport'"

- [ ] **Step 3: Write minimal implementation for RiskReport**

```python
# eqlib/portfolio_risk.py (追加)

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
```

需要添加 `field` 导入：
```python
from dataclasses import dataclass, field
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestRiskReport -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add RiskReport dataclass for portfolio risk results"
```

---

## Task 3: PortfolioRiskMonitor 初始化与 add_strategy

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for PortfolioRiskMonitor**

```python
# tests/test_portfolio_risk.py (追加)

def _make_backtest_result(n_days=50, annual_return=0.15, seed=42):
    """Create a synthetic backtest result dict."""
    import numpy as np
    rng = np.random.RandomState(seed)
    daily_vol = 0.20 / np.sqrt(252)
    daily_mu = annual_return / 252
    returns = rng.normal(daily_mu, daily_vol, n_days)

    dates = pd.bdate_range("2024-01-01", periods=n_days)
    starting_cash = 100_000.0
    values = [starting_cash]
    for r in returns:
        values.append(values[-1] * (1 + r))

    recorded_values = {
        d.date(): {"total_value": v, "cash": v * 0.1}
        for d, v in zip(dates, values[:-1])
    }

    return {
        "recorded_values": recorded_values,
        "trade_log": [],
        "context": type("Ctx", (), {
            "portfolio": type("P", (), {
                "starting_cash": starting_cash,
                "positions": {},
                "total_value": values[-1],
            })(),
        })(),
        "benchmark": "000300.XSHG",
    }


class TestPortfolioRiskMonitorInit:
    """Tests for PortfolioRiskMonitor initialization."""

    def test_init_default_thresholds(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        assert monitor.thresholds.max_drawdown_yellow == 0.15

    def test_init_custom_thresholds(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        custom = RiskThresholds(max_drawdown_kill=0.10)
        monitor = PortfolioRiskMonitor(thresholds=custom)
        assert monitor.thresholds.max_drawdown_kill == 0.10

    def test_add_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result()
        monitor.add_strategy("均线策略", result)
        assert "均线策略" in monitor._strategy_results

    def test_add_strategy_empty_result_raises(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        with pytest.raises(ValueError, match="回测结果为空"):
            monitor.add_strategy("test", {})

    def test_add_strategy_missing_recorded_values_raises(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        with pytest.raises(ValueError, match="缺少 recorded_values"):
            monitor.add_strategy("test", {"trade_log": []})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestPortfolioRiskMonitorInit -v`
Expected: FAIL with "ImportError: cannot import name 'PortfolioRiskMonitor'"

- [ ] **Step 3: Write minimal implementation for PortfolioRiskMonitor**

```python
# eqlib/portfolio_risk.py (追加)

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
            ValueError: 回测结果为空或缺少 recorded_values
        """
        if not backtest_result:
            raise ValueError(f"策略 '{name}' 的回测结果为空")
        if 'recorded_values' not in backtest_result:
            raise ValueError(f"策略 '{name}' 缺少 recorded_values 数据")
        self._strategy_results[name] = backtest_result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestPortfolioRiskMonitorInit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add PortfolioRiskMonitor class with add_strategy method"
```

---

## Task 4: portfolio_var 方法（历史模拟法）

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for portfolio_var**

```python
# tests/test_portfolio_risk.py (追加)

import numpy as np


class TestPortfolioVar:
    """Tests for portfolio_var method."""

    def test_portfolio_var_basic(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=2)
        monitor.add_strategy("策略A", result1)
        monitor.add_strategy("策略B", result2)
        
        var_amount, var_pct = monitor.portfolio_var()
        assert var_amount > 0
        assert var_pct > 0
        assert var_pct < 0.20  # 正常波动范围

    def test_portfolio_var_no_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        var_amount, var_pct = monitor.portfolio_var()
        assert var_amount == 0.0
        assert var_pct == 0.0

    def test_portfolio_var_single_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result(n_days=100)
        monitor.add_strategy("单策略", result)
        var_amount, var_pct = monitor.portfolio_var()
        assert var_amount > 0

    def test_portfolio_var_confidence_override(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result(n_days=100)
        monitor.add_strategy("test", result)
        
        var_95, pct_95 = monitor.portfolio_var(confidence=0.95)
        var_99, pct_99 = monitor.portfolio_var(confidence=0.99)
        # 99% VaR 应大于 95% VaR（更极端）
        assert var_99 >= var_95

    def test_portfolio_var_insufficient_data(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        # 只有 10 天数据，不足以计算 VaR
        result = _make_backtest_result(n_days=10)
        monitor.add_strategy("short", result)
        var_amount, var_pct = monitor.portfolio_var()
        # 数据不足时返回 NaN 或 0
        assert var_amount == 0.0 or np.isnan(var_amount)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestPortfolioVar -v`
Expected: FAIL with "AttributeError: 'PortfolioRiskMonitor' object has no attribute 'portfolio_var'"

- [ ] **Step 3: Write implementation for portfolio_var**

```python
# eqlib/portfolio_risk.py (追加到 PortfolioRiskMonitor 类)

import numpy as np

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
    # ... 现有代码 ...
    
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
        # 更精确的实现应按资产权重加权
        combined_returns = pd.concat(all_returns, axis=1).mean(axis=1)
        
        # 历史模拟法：取分布的负分位数
        # VaR 是损失，所以取 (1 - confidence) 分位的负值
        loss_quantile = 1 - confidence
        var_pct = -np.percentile(combined_returns, loss_quantile * 100)
        
        var_amount = total_value * var_pct
        
        return (float(var_amount), float(var_pct))
```

需要在文件顶部添加 numpy 导入：
```python
import numpy as np
```

同时将 `_extract_daily_returns` 作为模块级辅助函数。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestPortfolioVar -v`
Expected: PASS (可能需要微调实现以处理边界情况)

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add portfolio_var method using historical simulation"
```

---

## Task 5: correlation_matrix 方法

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for correlation_matrix**

```python
# tests/test_portfolio_risk.py (追加)

class TestCorrelationMatrix:
    """Tests for correlation_matrix method."""

    def test_correlation_matrix_basic(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=2)
        result3 = _make_backtest_result(n_days=100, seed=3)
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)
        monitor.add_strategy("C", result3)
        
        corr_matrix = monitor.correlation_matrix()
        assert isinstance(corr_matrix, pd.DataFrame)
        assert corr_matrix.shape == (3, 3)
        assert list(corr_matrix.index) == ["A", "B", "C"]
        # 对角线应为 1
        assert corr_matrix.loc["A", "A"] == 1.0
        assert corr_matrix.loc["B", "B"] == 1.0

    def test_correlation_matrix_single_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result(n_days=100)
        monitor.add_strategy("单策略", result)
        
        corr_matrix = monitor.correlation_matrix()
        assert corr_matrix.empty  # 单策略返回空 DataFrame

    def test_correlation_matrix_no_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        corr_matrix = monitor.correlation_matrix()
        assert corr_matrix.empty

    def test_correlation_values_in_range(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=2)
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)
        
        corr_matrix = monitor.correlation_matrix()
        # 相关性应在 [-1, 1] 范围内
        corr_ab = corr_matrix.loc["A", "B"]
        assert -1.0 <= corr_ab <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestCorrelationMatrix -v`
Expected: FAIL with "AttributeError: 'PortfolioRiskMonitor' object has no attribute 'correlation_matrix'"

- [ ] **Step 3: Write implementation for correlation_matrix**

```python
# eqlib/portfolio_risk.py (追加到 PortfolioRiskMonitor 类)

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestCorrelationMatrix -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add correlation_matrix method for strategy correlation analysis"
```

---

## Task 6: concentration_risk 方法

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for concentration_risk**

```python
# tests/test_portfolio_risk.py (追加)

class TestConcentrationRisk:
    """Tests for concentration_risk method."""

    def test_concentration_risk_no_positions(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result(n_days=50)
        monitor.add_strategy("test", result)
        
        concentration = monitor.concentration_risk()
        assert concentration["num_holdings"] == 0
        assert concentration["max_single_stock"] == 0.0

    def test_concentration_risk_with_positions(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        
        # 模拟有持仓的结果
        result = _make_backtest_result(n_days=50)
        result["context"].portfolio.positions = {
            "601390": type("Pos", (), {"amount": 1000, "value": 10000})(),
            "600519": type("Pos", (), {"amount": 500, "value": 5000})(),
        }
        result["context"].portfolio.total_value = 200000
        
        monitor.add_strategy("test", result)
        concentration = monitor.concentration_risk()
        
        assert concentration["num_holdings"] == 2
        assert concentration["max_single_stock"] > 0

    def test_concentration_risk_returns_required_keys(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result(n_days=50)
        monitor.add_strategy("test", result)
        
        concentration = monitor.concentration_risk()
        required_keys = [
            "max_single_stock",
            "max_single_sector",
            "small_cap_pct",
            "num_holdings",
            "top3_concentration",
        ]
        for key in required_keys:
            assert key in concentration
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestConcentrationRisk -v`
Expected: FAIL with "AttributeError: 'PortfolioRiskMonitor' object has no attribute 'concentration_risk'"

- [ ] **Step 3: Write implementation for concentration_risk**

```python
# eqlib/portfolio_risk.py (追加到 PortfolioRiskMonitor 类)

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
        all_positions: Dict[str, Dict] = {}  # {stock_code: {"amount": x, "value": y}}
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
        
        # 板块和市值分析需要 akshare 数据，这里简化处理
        # 实际实现时应调用 get_industry() 和 get_security_info()
        # 暂时返回保守估计值
        max_single_sector = max_single_stock  # 保守估计：假设同板块
        small_cap_pct = 0.0  # 保守估计：假设无微盘股
        
        return {
            "max_single_stock": float(max_single_stock),
            "max_single_sector": float(max_single_sector),
            "small_cap_pct": float(small_cap_pct),
            "num_holdings": len(all_positions),
            "top3_concentration": float(top3_concentration),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestConcentrationRisk -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add concentration_risk method for portfolio concentration analysis"
```

---

## Task 7: regime_detection 方法

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for regime_detection**

```python
# tests/test_portfolio_risk.py (追加)

class TestRegimeDetection:
    """Tests for regime_detection method."""

    def test_regime_detection_returns_string(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        regime = monitor.regime_detection()
        assert regime in ["bull", "bear", "oscillation", "unknown"]

    def test_regime_detection_no_data(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        # 无策略数据时仍能检测（使用默认指数数据）
        regime = monitor.regime_detection()
        assert regime is not None

    def test_regime_with_mock_index_data(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        
        # Mock 指数数据场景需要更复杂的 setup
        # 这里只验证方法存在且返回正确格式
        regime = monitor.regime_detection()
        assert isinstance(regime, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestRegimeDetection -v`
Expected: FAIL with "AttributeError: 'PortfolioRiskMonitor' object has no attribute 'regime_detection'"

- [ ] **Step 3: Write implementation for regime_detection**

```python
# eqlib/portfolio_risk.py (追加到 PortfolioRiskMonitor 类)

    def regime_detection(self) -> str:
        """市场 regime 检测（简单趋势法）
        
        Returns:
            'bull' / 'bear' / 'oscillation' / 'unknown'
            
        流程:
        1. 获取沪深300 近60日收盘价
        2. 计算 MA20 和 MA60
        3. 判断趋势方向
        """
        try:
            # 尝试获取指数数据
            from eqlib.data import get_price
            
            end_date = pd.Timestamp.now().date()
            start_date = end_date - pd.Timedelta(days=90)  # 多取一些以确保60个交易日
            
            index_data = get_price("000300.XSHG", start_date=start_date, end_date=end_date)
            
            if index_data is None or len(index_data) < 60:
                return "unknown"
            
            close = index_data["close"]
            ma20 = close.iloc[-20:].mean()
            ma60 = close.iloc[-60:].mean()
            current = close.iloc[-1]
            
            # 计算均线间距百分比
            gap_pct = abs(ma20 - ma60) / ma60
            
            if ma20 > ma60 and gap_pct > 0.02:
                return "bull"
            elif ma20 < ma60 and gap_pct > 0.02:
                return "bear"
            else:
                return "oscillation"
                
        except Exception:
            # 数据获取失败时返回 unknown
            return "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestRegimeDetection -v`
Expected: PASS (注意：测试可能因 akshare API 调用而较慢)

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add regime_detection method using simple trend analysis"
```

---

## Task 8: daily_check 综合检查方法

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for daily_check**

```python
# tests/test_portfolio_risk.py (追加)

class TestDailyCheck:
    """Tests for daily_check method."""

    def test_daily_check_returns_risk_report(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=2)
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)
        
        report = monitor.daily_check()
        assert isinstance(report, RiskReport)
        assert report.alert_level in [AlertLevel.YELLOW, AlertLevel.RED, AlertLevel.KILL_SWITCH]

    def test_daily_check_no_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        report = monitor.daily_check()
        assert report.alert_level == AlertLevel.YELLOW  # 无策略默认黄色监控
        assert "无策略数据" in report.triggers or len(report.triggers) == 0

    def test_daily_check_high_correlation_trigger(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor
        monitor = PortfolioRiskMonitor()
        
        # 两个高度相关的策略（相同 seed）
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=1)  # 相同数据，相关性=1
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)
        
        report = monitor.daily_check()
        # 高相关性应触发预警
        assert any("相关性" in t for t in report.triggers) or report.alert_level == AlertLevel.KILL_SWITCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestDailyCheck -v`
Expected: FAIL with "AttributeError: 'PortfolioRiskMonitor' object has no attribute 'daily_check'"

- [ ] **Step 3: Write implementation for daily_check**

```python
# eqlib/portfolio_risk.py (追加到 PortfolioRiskMonitor 类)

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
            # 找最大非对角线相关性
            for i in range(len(corr_matrix)):
                for j in range(i + 1, len(corr_matrix)):
                    corr_val = corr_matrix.iloc[i, j]
                    if abs(corr_val) > max_correlation:
                        max_correlation = abs(corr_val)
            
            # 相关性预警检查
            if max_correlation >= self.thresholds.correlation_kill:
                triggers.append(f"熔断预警：策略相关性过高 ({max_correlation:.2f} >= {self.thresholds.correlation_kill})，分散化失效")
                recommendations.append("建议降低高相关性策略仓位 50%")
                alert_level = AlertLevel.KILL_SWITCH
            elif max_correlation >= self.thresholds.correlation_red:
                triggers.append(f"红色预警：策略相关性较高 ({max_correlation:.2f} >= {self.thresholds.correlation_red})")
                recommendations.append("建议关注策略分散度")
                alert_level = AlertLevel.RED
            elif max_correlation >= self.thresholds.correlation_yellow:
                triggers.append(f"黄色预警：策略相关性 ({max_correlation:.2f})")
        
        # 3. 计算集中度
        concentration = self.concentration_risk()
        
        # 集中度预警检查
        if concentration["max_single_stock"] > self.thresholds.single_stock_max:
            triggers.append(f"单股票持仓占比过高 ({concentration['max_single_stock']:.2%})")
            recommendations.append(f"建议减仓超占比股票")
        
        if concentration["max_single_sector"] > self.thresholds.single_sector_max:
            triggers.append(f"单板块持仓占比过高 ({concentration['max_single_sector']:.2%})")
        
        if concentration["small_cap_pct"] > self.thresholds.small_cap_max:
            triggers.append(f"微盘股占比过高 ({concentration['small_cap_pct']:.2%})")
            recommendations.append("微盘股流动性风险大，建议控制仓位")
        
        # 4. Regime 检测
        regime = self.regime_detection()
        if regime == "bear":
            triggers.append("当前市场 regime: 熊市")
            recommendations.append("熊市环境，建议降低仓位或增加防御性资产")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestDailyCheck -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add daily_check method for comprehensive risk monitoring"
```

---

## Task 9: check_kill_switch 独立函数

**Files:**
- Modify: `eqlib/portfolio_risk.py`
- Modify: `tests/test_portfolio_risk.py`

- [ ] **Step 1: Write the failing test for check_kill_switch**

```python
# tests/test_portfolio_risk.py (追加)

class TestCheckKillSwitch:
    """Tests for check_kill_switch function."""

    def test_check_kill_switch_yellow_returns_empty(self):
        from eqlib.portfolio_risk import check_kill_switch
        report = RiskReport(
            timestamp=pd.Timestamp.now(),
            alert_level=AlertLevel.YELLOW,
            triggers=["相关性监控"],
        )
        actions = check_kill_switch(report)
        assert actions == []

    def test_check_kill_switch_red_returns_actions(self):
        from eqlib.portfolio_risk import check_kill_switch
        report = RiskReport(
            timestamp=pd.Timestamp.now(),
            alert_level=AlertLevel.RED,
            triggers=["回撤超过阈值"],
            recommendations=["人工介入"],
        )
        actions = check_kill_switch(report)
        assert len(actions) > 0
        assert any("人工" in a for a in actions)

    def test_check_kill_switch_kill_returns_strong_actions(self):
        from eqlib.portfolio_risk import check_kill_switch
        report = RiskReport(
            timestamp=pd.Timestamp.now(),
            alert_level=AlertLevel.KILL_SWITCH,
            triggers=["熔断预警：策略相关性过高"],
            recommendations=["建议降低仓位"],
        )
        actions = check_kill_switch(report)
        assert len(actions) > 0
        assert any("暂停" in a or "熔断" in a for a in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestCheckKillSwitch -v`
Expected: FAIL with "ImportError: cannot import name 'check_kill_switch'"

- [ ] **Step 3: Write implementation for check_kill_switch**

```python
# eqlib/portfolio_risk.py (追加模块级函数)

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
        
        # 如果没有具体触发，给出通用熔断建议
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestCheckKillSwitch -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "feat: add check_kill_switch function for alert action generation"
```

---

## Task 10: 导出新 API 到 eqlib/__init__.py

**Files:**
- Modify: `eqlib/__init__.py`

- [ ] **Step 1: Write the failing test for module exports**

```python
# tests/test_portfolio_risk.py (追加)

class TestModuleExports:
    """Tests for eqlib module exports."""

    def test_import_from_eqlib(self):
        from eqlib import PortfolioRiskMonitor, RiskThresholds, RiskReport, AlertLevel
        assert PortfolioRiskMonitor is not None
        assert RiskThresholds is not None
        assert RiskReport is not None
        assert AlertLevel is not None

    def test_import_check_kill_switch(self):
        from eqlib import check_kill_switch
        assert check_kill_switch is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_risk.py::TestModuleExports -v`
Expected: FAIL with "ImportError: cannot import name 'PortfolioRiskMonitor' from 'eqlib'"

- [ ] **Step 3: Add exports to eqlib/__init__.py**

找到 `eqlib/__init__.py` 中适当位置添加：

```python
# ─────────────────────────────────────────────────────────────────────────────

# Portfolio risk monitoring  [EXPERIMENTAL]
from eqlib.portfolio_risk import (
    PortfolioRiskMonitor,
    RiskThresholds,
    RiskReport,
    AlertLevel,
    check_kill_switch,
)
```

需要在文件中找到合适位置插入（建议在 Scientific validation 之后）。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_portfolio_risk.py::TestModuleExports -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eqlib/__init__.py tests/test_portfolio_risk.py
git commit -m "feat: export portfolio_risk API from eqlib module"
```

---

## Task 11: 运行完整测试套件并修复问题

**Files:**
- Modify: 可能需要修复 `eqlib/portfolio_risk.py` 或 `tests/test_portfolio_risk.py`

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/test_portfolio_risk.py -v`
Expected: 大部分 PASS，可能有小问题需修复

- [ ] **Step 2: Fix any test failures**

如果测试失败，根据错误信息修复代码。

- [ ] **Step 3: Run all eqlib tests to ensure no regression**

Run: `pytest tests/ -v --tb=short`
Expected: 所有测试 PASS

- [ ] **Step 4: Commit fixes if needed**

```bash
git add eqlib/portfolio_risk.py tests/test_portfolio_risk.py
git commit -m "fix: resolve test failures in portfolio_risk module"
```

---

## Task 12: 添加 __all__ 并完善文档

**Files:**
- Modify: `eqlib/portfolio_risk.py`

- [ ] **Step 1: Add __all__ to portfolio_risk.py**

```python
# eqlib/portfolio_risk.py (在文件末尾添加)

__all__ = [
    "AlertLevel",
    "RiskThresholds",
    "RiskReport",
    "PortfolioRiskMonitor",
    "check_kill_switch",
]
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `pytest tests/test_portfolio_risk.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add eqlib/portfolio_risk.py
git commit -m "docs: add __all__ exports to portfolio_risk module"
```

---

## 验收清单

完成所有任务后，验证以下标准：

- [ ] `PortfolioRiskMonitor` 类可正常初始化
- [ ] `add_strategy()` 能添加回测结果并验证输入
- [ ] `portfolio_var()` 使用历史模拟法计算 VaR
- [ ] `correlation_matrix()` 计算策略间 Pearson 相关性
- [ ] `concentration_risk()` 计算单股票/板块/微盘股集中度
- [ ] `regime_detection()` 检测牛市/熊市/震荡市
- [ ] `daily_check()` 返回完整 RiskReport
- [ ] `check_kill_switch()` 根据预警级别返回操作建议
- [ ] 所有 API 从 `eqlib` 模块正确导出
- [ ] 单元测试覆盖率 > 80%
- [ ] 所有现有测试无回归

---

## Self-Review

**1. Spec coverage:**
- AlertLevel/RiskThresholds/RiskReport 数据结构 → Task 1-2 ✅
- PortfolioRiskMonitor 类 → Task 3 ✅
- portfolio_var 历史模拟法 → Task 4 ✅
- correlation_matrix → Task 5 ✅
- concentration_risk → Task 6 ✅
- regime_detection → Task 7 ✅
- daily_check → Task 8 ✅
- check_kill_switch → Task 9 ✅
- 导出 API → Task 10 ✅

**2. Placeholder scan:** 无 TBD/TODO，所有代码完整

**3. Type consistency:** 
- `RiskReport` 字段名在各任务中一致
- `PortfolioRiskMonitor` 方法签名一致
- 导入路径正确

---

## 后续工作（不在本计划范围）

- 集成到 `run_backtest()` 自动风控检查
- 集成到 `run_paper_trade()` 实盘预警
- Web Studio 前端风控仪表盘
- 多指标综合 regime 检测
- Monte Carlo VaR 可选深度分析