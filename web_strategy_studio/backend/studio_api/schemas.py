"""Pydantic schemas aligned with design spec §4."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: str


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: Optional[list[ErrorDetail]] = None


class ErrorResponse(BaseModel):
    error: ErrorEnvelope


def api_error(code: str, message: str, details: Any = None) -> dict:
    """Build a standardised error envelope dict for HTTPException detail."""
    return {"error": {"code": code, "message": message, "details": details}}


class DefaultBacktestParams(BaseModel):
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    starting_cash: float = 100_000
    benchmark: str = "000300.XSHG"
    use_local: bool = False
    report_dir: Optional[str] = None
    securities: Optional[list[str]] = None
    max_memory_mb: int = 1024


class CreateStrategyBody(BaseModel):
    name: str
    description: Optional[str] = None
    source_code: str
    default_params: Optional[DefaultBacktestParams] = None


class StrategyCreated(BaseModel):
    id: str
    name: str
    version: int
    created_at: datetime


class StrategyDetail(BaseModel):
    id: str
    name: str
    description: Optional[str]
    source_code: str
    version: int
    updated_at: Optional[datetime]
    default_params: Optional[dict] = None


class StrategyVersionItem(BaseModel):
    """One entry in GET /strategies/{id}/versions."""

    version: int
    label: Optional[str] = None
    content_hash: Optional[str] = None
    created_at: datetime


class PatchStrategyBody(BaseModel):
    source_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class SnapshotBody(BaseModel):
    label: Optional[str] = None


class StrategyTemplateResponse(BaseModel):
    source_code: str
    hints: list[str]


class LintBody(BaseModel):
    source_code: str
    profile: Literal["fast", "strict"] = "fast"


class LintResponse(BaseModel):
    ok: bool
    syntax_errors: list[dict[str, Any]]
    lint_issues: list[dict[str, Any]]
    security_notes: list[dict[str, Any]]


class RunParams(BaseModel):
    start_date: str
    end_date: str
    starting_cash: float = 100_000
    benchmark: str = "000300.XSHG"
    use_local: bool = False
    report_dir: Optional[str] = None
    securities: Optional[list[str]] = None
    max_memory_mb: int = 1024


class CreateRunBody(BaseModel):
    strategy_id: str
    source_code: Optional[str] = None
    params: RunParams


class CreateRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    poll_url: str
    stream_url: str  # B16: renamed from ws_url
    queue_position: Optional[int] = None  # B18: 1-based position when queued


class RunArtifacts(BaseModel):
    html_report_url: Optional[str] = None
    json_report_url: Optional[str] = None


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    progress: float
    stage: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    artifacts: RunArtifacts
    error: Optional[str] = None
    queue_position: Optional[int] = None  # B18


class CompletionBody(BaseModel):
    source_code: str
    cursor_line: int = Field(ge=0)
    cursor_col: int = Field(ge=0)


class CompletionItem(BaseModel):
    label: str
    kind: str
    insert_text: str
    insert_text_format: Literal["snippet", "plain"] = "snippet"
    documentation: str = ""


class CompletionResponse(BaseModel):
    suggestions: list[CompletionItem]


class FormatBody(BaseModel):
    source_code: str


# ---------------------------------------------------------------------------
# Runs list & metrics (§4.5)
# ---------------------------------------------------------------------------


class RunListItem(BaseModel):
    """Minimal info for the history list sidebar."""

    run_id: str
    strategy_id: str
    strategy_name: Optional[str] = None
    status: str
    progress: float
    stage: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    queue_position: Optional[int] = None  # B18


class RunListResponse(BaseModel):
    runs: list[RunListItem]
    total: int


class MetricValue(BaseModel):
    name: str
    value: Optional[float] = None
    label: str = ""


class RunMetricsResponse(BaseModel):
    run_id: str
    status: str
    metrics: dict[str, Optional[float]]
    # Raw dict from report.json so the frontend can render any key
    raw: dict[str, Any] = Field(default_factory=dict)


class EquityCurvePoint(BaseModel):
    date: str
    value: float


class CompareRunItem(BaseModel):
    run_id: str
    strategy_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    metrics: dict[str, Optional[float]]
    equity_curve: list[EquityCurvePoint] = Field(default_factory=list)  # B22


class CompareResponse(BaseModel):
    runs: list[CompareRunItem]
    # Column names shared across all runs
    common_keys: list[str]


# ---------------------------------------------------------------------------
# Queue status (B17/B18)
# ---------------------------------------------------------------------------


class QueueRunItem(BaseModel):
    run_id: str
    queue_position: int


class QueueStatusResponse(BaseModel):
    queue_length: int
    active_count: int
    max_concurrent: int
    queued_runs: list[QueueRunItem]
