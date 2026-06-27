from __future__ import annotations

import re
from typing import Any, Callable

ALLOWED_TOOL_NAMES = {
    "mcp__restricted_etl__run_etl_pipeline",
    "run_etl_pipeline",
    "mcp__restricted_etl__send_telegram_report",
    "send_telegram_report",
}

DESTRUCTIVE_PATTERNS = re.compile(
    r"\b(rm|unlink|rmdir|del|remove|delete|drop|truncate|shutdown|reboot)\b",
    re.IGNORECASE,
)


def make_permission_handler(
    allow_cls: Callable[..., Any],
    deny_cls: Callable[..., Any],
) -> Callable[[str, dict[str, Any], Any], Any]:
    async def can_use_tool(tool_name: str, input_data: dict[str, Any], _context: Any) -> Any:
        if tool_name in ALLOWED_TOOL_NAMES:
            return allow_cls(updated_input=input_data)
        return deny_cls(message=f"Tool is not allowed: {tool_name}", interrupt=True)

    return can_use_tool


async def block_delete_hook(input_data: dict[str, Any], _tool_use_id: str | None, _context: Any) -> dict[str, Any]:
    tool_name = str(input_data.get("tool_name", ""))
    tool_input = input_data.get("tool_input", {})
    raw = f"{tool_name} {tool_input}"
    if DESTRUCTIVE_PATTERNS.search(raw):
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "deny",
                "permissionDecisionReason": "Delete/destructive operations are blocked for this agent.",
            }
        }
    return {}
