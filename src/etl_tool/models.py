from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Checkpoint(BaseModel):
    name: str
    status: Literal["ok", "failed"]
    detail: str = ""


class SavedFiles(BaseModel):
    csv_path: Path
    sqlite_path: Path


class QueryResult(BaseModel):
    name: str
    sql: str
    row_count: int
    columns: list[str]
    rows_preview: list[dict[str, Any]]


class ReportPeriod(BaseModel):
    label: str
    since_utc: str
    until_utc: str


class QuotaWindow(BaseModel):
    used: int | None = None
    limit: int | None = None
    remaining: int | None = None
    resets_at: str | None = None
    raw: dict[str, Any] | None = None


class QuotaInfo(BaseModel):
    status_code: int | None = None
    plan_type: str | None = None
    allowed: bool | None = None
    code_5h: QuotaWindow | None = None
    code_7d: QuotaWindow | None = None
    additional_rate_limits: Any = None
    error: str | None = None


class PipelineRunResult(BaseModel):
    status: Literal["ok", "failed"]
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    saved_files: SavedFiles | None = None
    extracted_rows: int = 0
    query_results: list[QueryResult] = Field(default_factory=list)
    summary: str = ""
    telegram_sent: bool = False
    report_period: ReportPeriod | None = None
    quota: QuotaInfo | None = None
    error: str | None = None


class AgentRunReport(BaseModel):
    status: Literal["ok", "failed"]
    checkpoints: list[Checkpoint]
    local_files: SavedFiles | None
    extracted_rows: int
    query_result_count: int
    summary: str
    telegram_sent: bool
    report_period: ReportPeriod | None = None
    quota: QuotaInfo | None = None
    error: str | None = None
