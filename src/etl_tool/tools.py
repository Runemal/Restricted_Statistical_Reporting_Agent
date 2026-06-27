from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import load_config
from .pipeline import run_pipeline
from .telegram import send_telegram_message


class RunEtlInput(BaseModel):
    config_path: str = Field(description="Path to the YAML ETL config.")
    queries_path: str = Field(description="Path to the read-only SQL query file.")
    send_telegram: bool = Field(
        default=False,
        description="Whether to send the deterministic pipeline summary directly to Telegram.",
    )


class SendTelegramInput(BaseModel):
    intro: str = Field(description="Short Russian ironic intro for the report.")


class _ToolRunState:
    def __init__(self) -> None:
        self.pipeline_result: Any = None


def build_mcp_server(config_path: str | Path, queries_path: str | Path):
    from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

    allowed_config_path = _resolved_path(config_path)
    allowed_queries_path = _resolved_path(queries_path)
    state = _ToolRunState()

    @tool(
        "run_etl_pipeline",
        "Run the fixed SSH/API/CSV/SQLite/query ETL pipeline without sending Telegram.",
        {"config_path": str, "queries_path": str, "send_telegram": bool},
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        ),
    )
    async def run_etl_pipeline(args: dict[str, Any]) -> dict:
        validated = RunEtlInput.model_validate(args)
        _assert_bound_path(validated.config_path, allowed_config_path, "config_path")
        _assert_bound_path(validated.queries_path, allowed_queries_path, "queries_path")
        if validated.send_telegram:
            raise ValueError("send_telegram must be false; use send_telegram_report after reviewing data")
        result = run_pipeline(
            allowed_config_path,
            allowed_queries_path,
            send_telegram=False,
        )
        state.pipeline_result = result
        payload = result.model_dump(mode="json")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False),
                }
            ],
            "data": payload,
        }

    @tool(
        "send_telegram_report",
        "Send the final report to Telegram by prepending the reviewed intro to the immutable pipeline summary.",
        {"intro": str},
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=True,
        ),
    )
    async def send_telegram_report(args: dict[str, Any]) -> dict:
        validated = SendTelegramInput.model_validate(args)
        if state.pipeline_result is None:
            raise ValueError("run_etl_pipeline must complete before send_telegram_report")
        if state.pipeline_result.status != "ok":
            raise ValueError("cannot send Telegram report for a failed pipeline run")
        message = compose_final_message(validated.intro, state.pipeline_result.summary)
        config = load_config(allowed_config_path)
        sent = send_telegram_message(config.telegram, message)
        payload = {"telegram_sent": sent, "summary": message}
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False),
                }
            ],
            "data": payload,
        }

    return create_sdk_mcp_server(
        name="restricted_etl",
        version="0.1.0",
        tools=[run_etl_pipeline, send_telegram_report],
    )


def compose_final_message(intro: str, summary: str) -> str:
    clean_intro = _clean_intro(intro)
    if not clean_intro:
        raise ValueError("intro must not be empty")
    return f"{clean_intro}\n\n{summary.strip()}"


def _clean_intro(value: str) -> str:
    lines = [line.strip().lstrip("#").strip() for line in value.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines[:2])[:500].strip()


def _resolved_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _assert_bound_path(value: str | Path, expected: Path, field_name: str) -> None:
    actual = _resolved_path(value)
    if actual != expected:
        raise ValueError(f"{field_name} is fixed for this agent run")
