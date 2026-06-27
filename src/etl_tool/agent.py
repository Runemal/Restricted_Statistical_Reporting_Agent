from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from .env import load_env_file
from .hooks import block_delete_hook, make_permission_handler
from .models import AgentRunReport, PipelineRunResult
from .tools import build_mcp_server


async def run_agent(config_path: Path, queries_path: Path, model: str | None = None) -> AgentRunReport:
    load_env_file()

    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

    prompt = (
        "Run the restricted ETL pipeline exactly once using run_etl_pipeline with "
        "send_telegram=false. Do not attempt file edits, shell commands, deletes, "
        "or any other tools. Use exactly the config_path and queries_path from the "
        "user message. After the tool returns, write only a short funny, ironic "
        "1-2 sentence intro in Russian for the report. The intro must be based only "
        "on returned facts, must not "
        "invent numbers, insult people, use profanity, or mention that data was saved. "
        "Then call send_telegram_report exactly once with only that intro. "
        "Do not rewrite, summarize, translate, remove, or reorder the pipeline summary; "
        "the send_telegram_report tool will append the immutable summary itself. "
        "Finally produce only the structured JSON report: copy the pipeline fields, "
        "set summary to the final Telegram message returned by send_telegram_report, "
        "set telegram_sent from "
        "send_telegram_report, and keep local_files null."
    )

    options = ClaudeAgentOptions(
        system_prompt=prompt,
        model=model or os.environ.get("CLAUDE_MODEL", "claude-sonnet"),
        mcp_servers={"restricted_etl": build_mcp_server(config_path, queries_path)},
        allowed_tools=[
            "mcp__restricted_etl__run_etl_pipeline",
            "mcp__restricted_etl__send_telegram_report",
        ],
        can_use_tool=make_permission_handler(PermissionResultAllow, PermissionResultDeny),
        hooks={"PreToolUse": [HookMatcher(hooks=[block_delete_hook])]},
        output_format={
            "type": "json_schema",
            "schema": AgentRunReport.model_json_schema(),
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            (
                f"config_path={config_path.as_posix()}\n"
                f"queries_path={queries_path.as_posix()}"
            )
        )
        state = _AgentRunState()
        async for message in client.receive_response():
            state.observe(message)
            parsed = _try_extract_structured_report(message)
            if parsed is not None:
                return parsed

    fallback = state.to_report()
    if fallback is not None:
        return fallback

    raise RuntimeError("Agent did not return a structured report")


class _AgentRunState:
    def __init__(self) -> None:
        self.pipeline_result: PipelineRunResult | None = None
        self.final_message: str | None = None
        self.telegram_sent: bool | None = None

    def observe(self, message: Any) -> None:
        for block in _message_blocks(message):
            tool_name = _tool_name(block)
            tool_input = _tool_input(block)
            if tool_name.endswith("send_telegram_report") and isinstance(tool_input, dict):
                intro_text = str(tool_input.get("intro", "")).strip()
                if intro_text and self.pipeline_result is not None:
                    self.final_message = f"{intro_text}\n\n{self.pipeline_result.summary}"

            payload = _payload_from_tool_result(block)
            if not isinstance(payload, dict):
                continue

            if "status" in payload and "query_results" in payload:
                try:
                    self.pipeline_result = PipelineRunResult.model_validate(payload)
                except Exception:
                    pass
                continue

            if "telegram_sent" in payload:
                self.telegram_sent = bool(payload["telegram_sent"])
                if isinstance(payload.get("summary"), str):
                    self.final_message = payload["summary"]
                continue

    def to_report(self) -> AgentRunReport | None:
        if self.pipeline_result is None:
            return None
        pipeline_result = self.pipeline_result
        return AgentRunReport(
            status=pipeline_result.status,
            checkpoints=pipeline_result.checkpoints,
            local_files=None,
            extracted_rows=pipeline_result.extracted_rows,
            query_result_count=len(pipeline_result.query_results),
            summary=self.final_message or pipeline_result.summary,
            telegram_sent=bool(self.telegram_sent),
            report_period=pipeline_result.report_period,
            quota=pipeline_result.quota,
            error=pipeline_result.error,
        )


def _try_extract_structured_report(message: Any) -> AgentRunReport | None:
    structured_output = getattr(message, "structured_output", None)
    if isinstance(structured_output, dict):
        return _report_from_payload(structured_output)

    if hasattr(message, "result") and isinstance(message.result, dict):
        return _report_from_payload(message.result)
    if hasattr(message, "result") and isinstance(message.result, str):
        parsed = _report_from_text(message.result)
        if parsed is not None:
            return parsed

    for block in _message_blocks(message):
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if not text:
            continue
        parsed = _report_from_text(text)
        if parsed is not None:
            return parsed
    return None


def _message_blocks(message: Any) -> list[Any]:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, list):
        return content
    return []


def _tool_name(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("name") or block.get("tool_name") or "")
    return str(getattr(block, "name", None) or getattr(block, "tool_name", None) or "")


def _tool_input(block: Any) -> Any:
    if isinstance(block, dict):
        return block.get("input") or block.get("tool_input")
    return getattr(block, "input", None) or getattr(block, "tool_input", None)


def _payload_from_tool_result(block: Any) -> dict[str, Any] | None:
    content = block.get("content") if isinstance(block, dict) else getattr(block, "content", None)
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            try:
                parsed = _json_from_text(str(item.get("text", "")))
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
    if isinstance(content, str):
        try:
            parsed = _json_from_text(content)
        except Exception:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _report_from_text(text: str) -> AgentRunReport | None:
    try:
        parsed = _json_from_text(text)
    except Exception:
        return None
    if isinstance(parsed, dict):
        try:
            return _report_from_payload(parsed)
        except Exception:
            return None
    return None


def _json_from_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def _report_from_payload(payload: dict[str, Any]) -> AgentRunReport:
    if "local_files" in payload and "query_result_count" in payload:
        return AgentRunReport.model_validate(payload)

    pipeline_result = PipelineRunResult.model_validate(payload)
    return AgentRunReport(
        status=pipeline_result.status,
        checkpoints=pipeline_result.checkpoints,
        local_files=pipeline_result.saved_files,
        extracted_rows=pipeline_result.extracted_rows,
        query_result_count=len(pipeline_result.query_results),
        summary=pipeline_result.summary,
        telegram_sent=pipeline_result.telegram_sent,
        report_period=pipeline_result.report_period,
        quota=pipeline_result.quota,
        error=pipeline_result.error,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the restricted Claude ETL agent.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--model", default=None)
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()
    report = asyncio.run(run_agent(args.config, args.queries, args.model))
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
