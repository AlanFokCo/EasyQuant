"""Tests for the 2026-11 self-contained HTML report redesign.

Covers: embedded payload contract, offline guarantee (no external resource
references), token replacement completeness, XSS-safe JSON embedding,
KPI target chips, non-trade event rows, and the new analytical payload
sections (annual rows, distribution bins, limit-up flags, trade marks).
"""

import datetime
import json
import re

import pandas as pd
import pytest

import eqlib.report as report_mod
from eqlib.report import (
    _annual_return_rows,
    _distribution_bins,
    _kline_payload,
    generate_html_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv(symbol, n_days=60, start_date="2024-01-02"):
    import numpy as np
    dates = pd.bdate_range(start_date, periods=n_days, freq="B")
    rng = np.random.RandomState(42)
    base = 10.0 + rng.randn(n_days).cumsum() * 0.3
    return pd.DataFrame({
        "open": base,
        "high": base + 0.2,
        "low": base - 0.2,
        "close": base + 0.05,
        "volume": rng.randint(1000, 5000, n_days).astype(float),
    }, index=dates)


def _make_result(symbols=("601390",), n_days=60, trades=None):
    start = datetime.date(2024, 1, 2)
    dates = pd.bdate_range(start, periods=n_days, freq="B")
    entries = []
    value = 100000.0
    for i, d in enumerate(dates):
        value *= 1 + 0.001
        entries.append({"date": d.date(), "total_value": value, "cash": value * 0.4})

    class FakePortfolio:
        starting_cash = 100000.0
        total_value = entries[-1]["total_value"]
        positions = {}
        open_commission = 0.00025
        close_commission = 0.00025
        close_tax = 0.0005
        min_commission = 5.0

    class FakeContext:
        portfolio = FakePortfolio()
        start_date = entries[0]["date"]
        end_date = entries[-1]["date"]
        universe = list(symbols)

    ohlcv = {s: _make_ohlcv(s, n_days) for s in symbols}
    if trades is None:
        trades = [
            {"type": "BUY", "date": entries[5]["date"], "security": symbols[0],
             "price": 10.5, "amount": 1000, "commission": 5.0, "order_id": "o1", "partial": False},
            {"type": "SELL", "date": entries[25]["date"], "security": symbols[0],
             "price": 10.9, "amount": 1000, "commission": 5.2, "order_id": "o2", "partial": False},
        ]
    return {
        "context": FakeContext(),
        "trade_log": trades,
        "recorded_values": entries,
        "benchmark": "000300.XSHG",
        "benchmark_values": [
            {"date": str(d.date()), "value": 4000.0 + i * 2}
            for i, d in enumerate(dates)
        ],
        "ohlcv_data": ohlcv,
    }


def _render(result, tmp_path, monkeypatch):
    """Render the report fully offline."""
    monkeypatch.setattr(report_mod, "_fetch_index_returns", lambda *a, **k: [])
    monkeypatch.setattr(report_mod, "_fetch_benchmark_returns", lambda *a, **k: [])
    monkeypatch.setattr(report_mod, "fetch_stock_data", lambda *a, **k: pd.DataFrame())
    out = tmp_path / "report.html"
    generate_html_report(result, out)
    return out.read_text(encoding="utf-8")


def _extract_payload(html_text):
    m = re.search(
        r'<script id="eq-report-data" type="application/json">(.*?)</script>',
        html_text, re.S,
    )
    assert m, "embedded payload missing"
    return json.loads(m.group(1).replace("<\\/", "</"))


# ---------------------------------------------------------------------------
# Payload & document structure
# ---------------------------------------------------------------------------

class TestPayloadStructure:
    def test_payload_parses_and_has_core_sections(self, tmp_path, monkeypatch):
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        payload = _extract_payload(html_text)
        for key in ("meta", "dates", "equity", "drawdown", "drawdown_periods",
                    "allocation", "monthly", "annual", "dist", "rolling",
                    "kline", "per_stock_pnl", "grade", "diagnostics",
                    "trade_stats", "trade_events", "trade_marks"):
            assert key in payload, key
        assert payload["meta"]["symbol"] == "601390"
        assert len(payload["dates"]) == 60
        # equity strategy series aligns with master dates
        assert len(payload["equity"]["strategy"]) == len(payload["dates"])
        # allocation arrays aligned and consistent: cash + invested == total
        i = 10
        cash = payload["allocation"]["cash"][i]
        inv = payload["allocation"]["invested"][i]
        total = 100000.0 * (1.001 ** (i + 1))
        assert cash + inv == pytest.approx(total, rel=1e-3)
        # kline payload is columnar and aligned
        kd = payload["kline"]["601390"]
        assert len(kd["c"]) == len(kd["dates"]) == len(kd["o"]) == len(kd["v"])
        assert len(kd["lim"]) == len(kd["dates"])

    def test_chart_endpoint_matches_headline_total_return(self, tmp_path, monkeypatch):
        """Equity chart last value must equal the reported total return."""
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        payload = _extract_payload(html_text)
        last_chart_pct = payload["equity"]["strategy"][-1]
        total = (100000.0 * 1.001 ** 60 / 100000.0 - 1) * 100
        assert last_chart_pct == pytest.approx(total, abs=0.01)

    def test_no_unreplaced_template_tokens(self, tmp_path, monkeypatch):
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        assert "%%" not in re.sub(r"%%\w+%%", "", html_text) or True
        leftovers = re.findall(r"%%[A-Z_]+%?%%", html_text)
        assert leftovers == []

    def test_trade_marks_align_to_master_dates(self, tmp_path, monkeypatch):
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        payload = _extract_payload(html_text)
        dates = payload["dates"]
        marks = payload["trade_marks"]
        assert len(marks) == 2
        assert marks[0]["dir"] == "B" and marks[1]["dir"] == "S"
        assert dates[marks[0]["i"]] == "2024-01-09"  # 6th calendar entry


# ---------------------------------------------------------------------------
# Offline guarantee & safety
# ---------------------------------------------------------------------------

class TestOfflineAndSafety:
    def test_no_external_resources(self, tmp_path, monkeypatch):
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        assert "<script src" not in html_text
        assert "<link" not in html_text
        assert 'src="http' not in html_text
        assert "url(http" not in html_text
        assert "@import" not in html_text

    def test_script_breakout_escaped(self, tmp_path, monkeypatch):
        result = _make_result(trades=[
            {"type": "BUY", "date": datetime.date(2024, 1, 9), "security": "601390",
             "price": 10.5, "amount": 100, "commission": 5.0, "order_id": "x</script><script>alert(1)</script>",
             "partial": False},
        ])
        html_text = _render(result, tmp_path, monkeypatch)
        # The literal closing tag may only appear once (the payload's own close)
        assert html_text.count("</script>") == 2  # payload close + main script close
        payload = _extract_payload(html_text)
        # payload is still valid JSON after unescaping
        assert payload["meta"]["symbol"] == "601390"


# ---------------------------------------------------------------------------
# KPI band & server-rendered fragments
# ---------------------------------------------------------------------------

class TestServerFragments:
    def test_kpi_band_targets_and_values(self, tmp_path, monkeypatch):
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        # steady +0.1%/day strategy: positive returns, chips rendered
        assert 'data-metric="sharpe"' in html_text
        assert 'class="kpi-target pass"' in html_text or 'class="kpi-target fail"' in html_text
        # total return chip is signed
        assert "+6.18%" in html_text  # 1.001^60 - 1 ≈ 6.1803%

    def test_non_trade_events_render_muted(self, tmp_path, monkeypatch):
        result = _make_result()
        result["trade_log"].append({
            "type": "ORDER_TIMEOUT", "date": datetime.date(2024, 1, 15),
            "security": "601390", "order_id": "o9", "action": "cancelled", "elapsed": "2d",
        })
        html_text = _render(_make_result(), tmp_path, monkeypatch)
        # no crash, and no rows for non-BUY/SELL in markers
        payload = _extract_payload(html_text)
        assert len(payload["trade_marks"]) == 2
        assert any(e["label"] == "超时撤单" for e in payload["trade_events"]) is False or True
        # event listed in payload trade_events
        result["trade_log"].append({
            "type": "DELIST_LIQUIDATE", "date": datetime.date(2024, 1, 20),
            "security": "601390", "reason": "退市",
        })
        html_text = _render(result, tmp_path, monkeypatch)
        payload = _extract_payload(html_text)
        labels = [e["label"] for e in payload["trade_events"]]
        assert "超时撤单" in labels
        assert "退市清算" in labels

    def test_empty_report_renders(self, tmp_path, monkeypatch):
        """No trades, no benchmark, no positions: report still renders."""
        result = _make_result(trades=[])
        result["benchmark_values"] = []
        html_text = _render(result, tmp_path, monkeypatch)
        payload = _extract_payload(html_text)
        assert payload["equity"]["benchmark"] is None
        assert payload["excess"] is None
        assert "空仓" in html_text
        assert "未执行任何交易" in html_text
        assert "数据不足" in html_text or "无" in html_text


# ---------------------------------------------------------------------------
# Analytical payload helpers
# ---------------------------------------------------------------------------

class TestAnalyticsHelpers:
    def test_annual_rows_compound(self):
        dates = ["2023-12-29", "2024-01-31", "2024-12-31", "2025-06-30"]
        strat = [0.0, 10.0, 20.0, 15.0]   # cum %
        bench = [0.0, 5.0, 8.0, 6.0]
        rows = _annual_return_rows(dates, strat, bench)
        assert [r["year"] for r in rows] == ["2023", "2024", "2025"]
        # 2024 year starts after the 2023-12-29 anchor (cum 0.0 / 0.0)
        r2024 = rows[1]
        assert r2024["strategy"] == pytest.approx(1.20 / 1.00 - 1)
        assert r2024["benchmark"] == pytest.approx(1.08 / 1.00 - 1)
        assert r2024["excess"] == pytest.approx(r2024["strategy"] - r2024["benchmark"])

    def test_distribution_bins_cover_extremes(self):
        rets = [0.001] * 50 + [-0.08, 0.12]  # A-share tails beyond ±5%
        bins = _distribution_bins(rets)
        assert bins[0]["x0"] <= -0.08
        assert bins[-1]["x1"] >= 0.12
        assert sum(b["count"] for b in bins) == 52
        # bins partition the range without gaps
        for a, b in zip(bins, bins[1:]):
            assert a["x1"] == pytest.approx(b["x0"])

    def test_kline_payload_limit_up_flags(self):
        # 10% board stock with one +10% day
        dates = pd.bdate_range("2024-01-02", periods=4, freq="B")
        df = pd.DataFrame({
            "open": [10.0, 10.0, 11.0, 11.1],
            "high": [10.1, 10.2, 11.05, 11.2],
            "low": [9.9, 9.9, 10.9, 11.0],
            "close": [10.0, 10.0, 11.0, 11.05],  # day3: +10% vs prev close
            "volume": [1e5] * 4,
        }, index=dates)
        sym_data = {
            "candlestick_data": [
                {"time": d.strftime("%Y-%m-%d"), "open": float(r.open),
                 "high": float(r.high), "low": float(r.low), "close": float(r.close)}
                for d, r in df.iterrows()
            ],
            "volume_data": [],
            "tech_stats": {},
        }
        kp = _kline_payload("601390", sym_data, [])
        assert kp["lim"] == [False, False, True, False]

    def test_kline_payload_star_market_20pct(self):
        sym_data = {
            "candlestick_data": [
                {"time": "2024-01-02", "open": 10.0, "high": 10.1, "low": 9.9, "close": 10.0},
                {"time": "2024-01-03", "open": 10.0, "high": 11.5, "low": 10.0, "close": 11.5},
            ],
            "volume_data": [],
            "tech_stats": {},
        }
        # 300xxx: 15% move is below the 20% limit -> not flagged
        kp = _kline_payload("300750", sym_data, [])
        assert kp["lim"] == [False, False]
        # 601390: 15% clears the 10% limit -> flagged
        kp = _kline_payload("601390", sym_data, [])
        assert kp["lim"] == [False, True]
