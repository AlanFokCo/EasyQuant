"""Data models shared by dependency evaluator checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import platform
from typing import Any


class Severity(str, Enum):
    """Severity levels ordered from blocking to advisory."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @property
    def rank(self) -> int:
        """Return the stable sort rank for this severity."""
        return {self.P0: 0, self.P1: 1, self.P2: 2, self.P3: 3}[self]


@dataclass(frozen=True)
class Finding:
    """A stable evaluator finding with its supporting evidence."""

    id: str
    severity: Severity
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    status: str = "open"


@dataclass
class EvaluationReport:
    """Results collected by one evaluator run."""

    profile: str
    started_at: str
    environment: dict[str, str]
    findings: list[Finding]

    @classmethod
    def create(cls, profile: str, findings: list[Finding]) -> EvaluationReport:
        """Create a report with the current UTC timestamp and environment."""
        return cls(
            profile=profile,
            started_at=datetime.now(timezone.utc).isoformat(),
            environment=environment_snapshot(),
            findings=findings,
        )

    def ordered_findings(self) -> list[Finding]:
        """Return findings ordered by severity and then stable identifier."""
        return sorted(self.findings, key=lambda item: (item.severity.rank, item.id))


def environment_snapshot() -> dict[str, str]:
    """Collect the minimal runtime evidence needed to identify a report run."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
