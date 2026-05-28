import numpy as np
import pandas as pd

from eqlib.scientific.comparison import (
    ComparisonJudgment,
    ComparisonReport,
    align_benchmark,
    compare_metrics,
    compare_with_platform,
    verify_trades,
)


def _sample_backtest_result() -> dict:
    values = [100000, 101000, 102000, 101500, 103000, 104500]
    dates = pd.bdate_range("2024-01-02", periods=len(values))
    recorded_values = [
        {"date": date, "total_value": value, "cash": value * 0.2}
        for date, value in zip(dates, values)
    ]
    trade_log = [
        {
            "date": dates[1],
            "type": "buy",
            "security": "000001.XSHE",
            "price": 10.0,
            "amount": 100,
            "commission": 1.0,
        },
        {
            "date": dates[3],
            "type": "sell",
            "security": "000001.XSHE",
            "price": 10.3,
            "amount": 100,
            "commission": 1.0,
        },
    ]
    return {
        "recorded_values": recorded_values,
        "trade_log": trade_log,
        "benchmark": "000300.XSHG",
    }


def test_align_benchmark_detects_aligned_series():
    dates = pd.bdate_range("2024-01-01", periods=5)
    local = pd.Series([100, 101, 102, 103, 104], index=dates)
    platform = pd.Series([200, 202, 204, 206, 208], index=dates)

    result = align_benchmark(local, platform)

    assert result.is_aligned is True
    assert result.correlation > 0.99
    assert result.max_deviation_pct < 1.0


def test_compare_metrics_returns_expected_judgment():
    local = {"total_return": 0.10, "sharpe_ratio": 1.20, "max_drawdown": -0.08}
    platform = {"total_return": 0.104, "sharpe_ratio": 1.18, "max_drawdown": -0.081}

    result = compare_metrics(local, platform)

    assert len(result.comparisons) == 3
    assert result.judgment == ComparisonJudgment.RESULT_ALIGNED
    assert result.max_deviation_pct < 5.0


def test_verify_trades_detects_price_and_amount_mismatch():
    dates = pd.bdate_range("2024-01-02", periods=2)
    local_trades = [
        {"date": dates[0], "type": "buy", "security": "AAA", "price": 10.00, "amount": 100},
        {"date": dates[1], "type": "sell", "security": "AAA", "price": 10.20, "amount": 100},
    ]
    platform_trades = [
        {"date": dates[0], "type": "buy", "security": "AAA", "price": 10.00, "amount": 100},
        {"date": dates[1], "type": "sell", "security": "AAA", "price": 10.50, "amount": 120},
    ]

    result = verify_trades(local_trades, platform_trades, price_tolerance=0.01)

    assert result.matched_count == 2
    assert result.is_consistent is False
    assert len(result.price_discrepancies) == 1
    assert result.price_discrepancies[0]["reason"] in {"price_mismatch", "amount_mismatch"}


def test_compare_with_platform_uses_metrics_and_equity_curve():
    local_result = _sample_backtest_result()
    dates = pd.to_datetime([row["date"] for row in local_result["recorded_values"]])
    local_values = pd.Series([row["total_value"] for row in local_result["recorded_values"]], index=dates)
    platform_values = local_values * 1.002

    comparison = compare_with_platform(
        local_result,
        {
            "total_return": 0.045,
            "annual_return": 5.35,
            "sharpe_ratio": 9.0,
            "max_drawdown": -0.005,
            "daily_values": platform_values,
        },
        platform_name="JoinQuant",
    )

    assert comparison.platform_name == "JoinQuant"
    assert len(comparison.metric_comparisons) == 4
    assert comparison.equity_correlation is not None
    assert comparison.equity_correlation > 0.99


def test_comparison_report_summary_includes_sections():
    local_result = _sample_backtest_result()
    comparison = compare_with_platform(local_result, {"total_return": 0.045, "sharpe_ratio": 9.0, "max_drawdown": -0.005, "annual_return": 5.35})
    report = ComparisonReport(
        comparison_result=comparison,
        metrics_comparison=compare_metrics({"total_return": 0.10}, {"total_return": 0.11}),
        trade_verification=verify_trades(local_result["trade_log"], local_result["trade_log"]),
    )

    summary = report.summary()

    assert "platform=" in summary
    assert "metric_max_dev=" in summary
    assert "trades=consistent" in summary
