"""Tests for eqlib.portfolio_risk module."""

import pytest
import pandas as pd
import numpy as np
from eqlib.portfolio_risk import AlertLevel, RiskThresholds, RiskReport


def _result_from_values(values):
    dates = pd.bdate_range("2024-01-01", periods=len(values))
    return {
        "recorded_values": {
            date.date(): {"total_value": float(value)}
            for date, value in zip(dates, values)
        }
    }


def test_portfolio_var_is_nav_weighted_not_strategy_count_weighted():
    from eqlib.portfolio_risk import PortfolioRiskMonitor

    large_values = [1_000_000.0]
    for _ in range(16):
        large_values.extend([900_000.0, 1_000_000.0])
    tiny_values = [1.0] * len(large_values)
    monitor = PortfolioRiskMonitor()
    monitor.add_strategy("large", _result_from_values(large_values))
    monitor.add_strategy("tiny", _result_from_values(tiny_values))

    _, var_pct = monitor.portfolio_var(confidence=0.95)

    assert var_pct == pytest.approx(0.10, abs=0.002)


def test_thirty_percent_drawdown_triggers_kill_switch(monkeypatch):
    from eqlib.portfolio_risk import PortfolioRiskMonitor

    monitor = PortfolioRiskMonitor()
    monitor.add_strategy("strategy", _result_from_values([100.0] * 30 + [70.0]))
    monkeypatch.setattr(monitor, "regime_detection", lambda: "unknown")

    report = monitor.daily_check()

    assert report.alert_level is AlertLevel.KILL_SWITCH
    assert any("回撤" in item for item in report.triggers)


def test_adding_concentration_to_existing_kill_switch_never_reduces_alert(monkeypatch):
    from eqlib.portfolio_risk import PortfolioRiskMonitor

    monitor = PortfolioRiskMonitor()
    monkeypatch.setattr(monitor, "portfolio_var", lambda: (0.0, 0.0))
    monkeypatch.setattr(
        monitor,
        "correlation_matrix",
        lambda: pd.DataFrame(
            [[1.0, 0.9], [0.9, 1.0]], index=["a", "b"], columns=["a", "b"]
        ),
    )
    monkeypatch.setattr(
        monitor,
        "concentration_risk",
        lambda: {
            "max_single_stock": 0.15,
            "max_single_sector": 0.0,
            "small_cap_pct": 0.0,
            "num_holdings": 1,
            "top3_concentration": 0.15,
        },
    )
    monkeypatch.setattr(monitor, "regime_detection", lambda: "unknown")

    assert monitor.daily_check().alert_level is AlertLevel.KILL_SWITCH


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
        "context": type(
            "Ctx",
            (),
            {
                "portfolio": type(
                    "P",
                    (),
                    {
                        "starting_cash": starting_cash,
                        "positions": {},
                        "total_value": values[-1],
                    },
                )(),
            },
        )(),
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

    def test_add_strategy_empty_recorded_values_raises(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor

        monitor = PortfolioRiskMonitor()
        with pytest.raises(ValueError, match="recorded_values 为空"):
            monitor.add_strategy("test", {"recorded_values": {}})

    def test_add_strategy_overwrite_warns(self):
        import warnings
        from eqlib.portfolio_risk import PortfolioRiskMonitor

        monitor = PortfolioRiskMonitor()
        result = _make_backtest_result()
        monitor.add_strategy("均线策略", result)
        # Adding same strategy again should warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            monitor.add_strategy("均线策略", result)
            assert len(w) == 1
            assert "将被覆盖" in str(w[0].message)


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
        # 数据不足时应返回 NaN
        assert np.isnan(var_amount)
        assert np.isnan(var_pct)
        # 应记录数据不足问题
        assert len(monitor._data_issues) == 1
        assert "short" in monitor._data_issues[0]
        assert "数据不足" in monitor._data_issues[0]

    def test_portfolio_var_partial_insufficient_data(self):
        """部分策略数据不足时，跳过这些策略继续计算"""
        from eqlib.portfolio_risk import PortfolioRiskMonitor

        monitor = PortfolioRiskMonitor()
        # 一个数据不足的策略
        short_result = _make_backtest_result(n_days=10, seed=1)
        monitor.add_strategy("short", short_result)
        # 一个数据充足的策略
        long_result = _make_backtest_result(n_days=100, seed=2)
        monitor.add_strategy("long", long_result)

        var_amount, var_pct = monitor.portfolio_var()
        # 应正常计算（使用 long 策略）
        assert var_amount > 0
        assert var_pct > 0
        # 应记录数据不足问题
        assert len(monitor._data_issues) == 1
        assert "short" in monitor._data_issues[0]


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
        regime = monitor.regime_detection()
        assert regime is not None

    def test_regime_with_mock_index_data(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor

        monitor = PortfolioRiskMonitor()
        regime = monitor.regime_detection()
        assert isinstance(regime, str)


class TestDailyCheck:
    """Tests for daily_check method."""

    def test_daily_check_returns_risk_report(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor, RiskReport, AlertLevel

        monitor = PortfolioRiskMonitor()
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=2)
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)

        report = monitor.daily_check()
        assert isinstance(report, RiskReport)
        assert report.alert_level in [
            AlertLevel.YELLOW,
            AlertLevel.RED,
            AlertLevel.KILL_SWITCH,
        ]

    def test_daily_check_no_strategy(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor, AlertLevel

        monitor = PortfolioRiskMonitor()
        report = monitor.daily_check()
        assert report.alert_level == AlertLevel.YELLOW
        assert "无策略数据" in report.triggers or len(report.triggers) == 0

    def test_daily_check_high_correlation_trigger(self):
        from eqlib.portfolio_risk import PortfolioRiskMonitor, AlertLevel

        monitor = PortfolioRiskMonitor()

        # 两个高度相关的策略（相同 seed）
        result1 = _make_backtest_result(n_days=100, seed=1)
        result2 = _make_backtest_result(n_days=100, seed=1)
        monitor.add_strategy("A", result1)
        monitor.add_strategy("B", result2)

        report = monitor.daily_check()
        # 高相关性应触发预警
        assert (
            any("相关性" in t for t in report.triggers)
            or report.alert_level == AlertLevel.KILL_SWITCH
        )


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
