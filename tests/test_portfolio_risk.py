"""Tests for eqlib.portfolio_risk module."""

import pytest
import pandas as pd
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