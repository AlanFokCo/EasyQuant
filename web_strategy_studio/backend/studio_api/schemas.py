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


class PatchStrategyBody(BaseModel):
    source_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


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
    ws_url: str  # spec name; MVP uses SSE at same path pattern


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
