"""Freshness checks for the packaged A-share exchange calendar."""

from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path

from .models import Finding, Severity


_CALENDAR_RESOURCE = Path("eqlib/static/ashare_trading_days.json")


def evaluate_calendar_coverage(
    root: Path, *, today: date | None = None, warning_days: int = 120
) -> list[Finding]:
    """Report invalid or soon-to-expire bundled exchange-calendar coverage."""
    reference_date = today or date.today()
    path = Path(root) / _CALENDAR_RESOURCE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        coverage_end = date.fromisoformat(payload["coverage"]["end"])
    except (OSError, TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return [
            Finding(
                "DATA-191",
                Severity.P1,
                "Bundled exchange calendar is invalid",
                "The offline A-share trading-calendar metadata cannot be read.",
                evidence={"path": str(path), "error": str(exc)},
                remediation="Regenerate eqlib/static/ashare_trading_days.json before release.",
            )
        ]

    required_end = reference_date + timedelta(days=warning_days)
    if coverage_end < required_end:
        return [
            Finding(
                "DATA-192",
                Severity.P2,
                "Bundled exchange calendar expires soon",
                f"Coverage ends on {coverage_end.isoformat()}, before the {warning_days}-day release horizon.",
                evidence={
                    "coverage_end": coverage_end.isoformat(),
                    "required_end": required_end.isoformat(),
                },
                remediation="Refresh the bundled A-share trading calendar before the coverage window expires.",
            )
        ]
    return []
