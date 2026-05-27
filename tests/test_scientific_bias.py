import pandas as pd

from eqlib.scientific.bias import (
    BiasReport,
    BiasSeverity,
    SurvivorshipCorrectedData,
    check_data_bias,
    check_lookahead_bias,
    check_selection_bias,
    check_survivorship_bias,
)


class _Context:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date


def test_check_survivorship_bias_flags_small_pool_and_late_entries():
    result = check_survivorship_bias(
        stock_pool={
            "AAA": pd.DataFrame(
                {"close": [10, 11]},
                index=pd.to_datetime(["2024-03-15", "2024-03-18"]),
            ),
            "BBB": pd.DataFrame(
                {"close": [20, 21]},
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            ),
            "CCC": pd.DataFrame(
                {"close": [30, 31]},
                index=pd.to_datetime(["2024-04-01", "2024-04-02"]),
            ),
        },
        start_date="2024-01-01",
        end_date="2024-06-30",
    )

    assert result.bias_type == "survivorship"
    assert result.detected is True
    assert result.severity >= BiasSeverity.HIGH
    assert result.recommendations


def test_check_lookahead_bias_flags_trades_outside_range_and_first_day():
    ohlcv = {
        "AAA": pd.DataFrame(
            {
                "open": [10, 10.5],
                "high": [11, 11],
                "low": [9.5, 10],
                "close": [10.8, 10.7],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
    }
    result = check_lookahead_bias(
        backtest_result={
            "recorded_values": [
                {"date": "2024-01-02", "total_value": 100000, "cash": 100000},
                {"date": "2024-01-03", "total_value": 130000, "cash": 1000},
                {"date": "2024-01-04", "total_value": 165000, "cash": 1000},
            ],
            "trade_log": [
                {
                    "date": "2024-01-02",
                    "type": "BUY",
                    "security": "AAA",
                    "price": 12.5,
                    "amount": 100,
                    "commission": 1,
                }
            ],
            "context": _Context("2024-01-02", "2024-01-04"),
            "ohlcv_data": ohlcv,
        },
        data_usage_log=["feature uses shift(-1) for labels"],
    )

    assert result.bias_type == "lookahead"
    assert result.detected is True
    assert result.severity >= BiasSeverity.HIGH
    assert "OHLC" in result.details or "first backtest day" in result.details


def test_check_selection_bias_flags_aggressive_filtering_and_narrow_trading():
    result = check_selection_bias(
        backtest_result={
            "trade_log": [
                {"security": "AAA"},
                {"security": "AAA"},
                {"security": "BBB"},
            ]
        },
        filter_conditions=["pe < 20"] * 8,
        universe_size=500,
        filtered_size=5,
    )

    assert result.bias_type == "selection"
    assert result.detected is True
    assert result.severity >= BiasSeverity.HIGH


def test_check_data_bias_flags_gaps_constant_values_and_anomalies():
    result = check_data_bias(
        {
            "recorded_values": [
                {"date": "2024-01-01", "total_value": 100000, "cash": 100000},
                {"date": "2024-01-02", "total_value": 100000, "cash": 100000},
                {"date": "2024-01-20", "total_value": 100000, "cash": 100000},
                {"date": "2024-01-21", "total_value": 140000, "cash": 100000},
            ],
            "context": _Context("2024-01-01", "2024-01-21"),
        }
    )

    assert result.bias_type == "data"
    assert result.detected is True
    assert result.severity >= BiasSeverity.MEDIUM
    assert result.recommendations


def test_bias_report_and_stub_class():
    checks = [
        check_selection_bias(universe_size=100, filtered_size=100),
        check_data_bias(
            {
                "recorded_values": [
                    {"date": "2024-01-01", "total_value": 100000},
                    {"date": "2024-01-02", "total_value": 101000},
                    {"date": "2024-01-03", "total_value": 102000},
                    {"date": "2024-01-04", "total_value": 103000},
                    {"date": "2024-01-05", "total_value": 104000},
                    {"date": "2024-01-06", "total_value": 105000},
                    {"date": "2024-01-07", "total_value": 106000},
                    {"date": "2024-01-08", "total_value": 107000},
                    {"date": "2024-01-09", "total_value": 108000},
                    {"date": "2024-01-10", "total_value": 109000},
                    {"date": "2024-01-11", "total_value": 110000},
                    {"date": "2024-01-12", "total_value": 111000},
                    {"date": "2024-01-13", "total_value": 112000},
                    {"date": "2024-01-14", "total_value": 113000},
                ],
                "context": _Context("2024-01-01", "2024-01-14"),
            }
        ),
    ]
    report = BiasReport(checks=checks)
    stub = SurvivorshipCorrectedData("2024-01-01", "2024-12-31")

    assert report.overall_severity == max(c.severity for c in checks)
    assert isinstance(report.summary(), str)
    assert stub.note.startswith("Survivorship correction")
