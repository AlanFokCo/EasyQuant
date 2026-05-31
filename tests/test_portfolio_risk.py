"""Tests for eqlib.portfolio_risk module."""

import pytest
import pandas as pd
import numpy as np
from eqlib.portfolio_risk import AlertLevel, RiskThresholds


def _make_backtest_result(n_days=50, annual_return=0.15, seed=42):
    """Create a synthetic backtest result dict."""
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