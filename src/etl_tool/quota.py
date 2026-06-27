from __future__ import annotations

import os
from typing import Any

import httpx

from .models import QuotaInfo, QuotaWindow


def fetch_quota_info() -> QuotaInfo | None:
    if os.environ.get("CPA_QUOTA_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return None

    management_key = os.environ.get("CPA_MANAGEMENT_KEY")
    if not management_key:
        return QuotaInfo(error="CPA_MANAGEMENT_KEY не задан")

    missing = [
        name
        for name in ("CPA_BASE_URL", "AUTH_INDEX", "CHATGPT_ACCOUNT_ID")
        if not os.environ.get(name)
    ]
    if missing:
        return QuotaInfo(error=f"не заданы параметры лимитов: {', '.join(missing)}")

    base_url = os.environ["CPA_BASE_URL"].rstrip("/")
    auth_index = os.environ["AUTH_INDEX"]
    account_id = os.environ["CHATGPT_ACCOUNT_ID"]

    payload = {
        "auth_index": auth_index,
        "method": "GET",
        "url": "https://chatgpt.com/backend-api/wham/usage",
        "header": {
            "Authorization": "Bearer $TOKEN$",
            "Content-Type": "application/json",
            "User-Agent": "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal",
            "Chatgpt-Account-Id": account_id,
        },
    }

    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"{base_url}/v0/management/api-call",
                headers={
                    "Authorization": f"Bearer {management_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return QuotaInfo(error=f"не удалось получить лимиты: {exc}")

    body = data.get("body")
    if isinstance(body, str):
        try:
            body = httpx.Response(200, content=body).json()
        except Exception:
            body = {}
    if not isinstance(body, dict):
        body = {}

    rate_limit = body.get("rate_limit") if isinstance(body.get("rate_limit"), dict) else {}
    return QuotaInfo(
        status_code=_int_or_none(data.get("status_code")),
        plan_type=_str_or_none(body.get("plan_type")),
        allowed=_bool_or_none(rate_limit.get("allowed")),
        code_5h=_window(rate_limit.get("primary_window")),
        code_7d=_window(rate_limit.get("secondary_window")),
        additional_rate_limits=body.get("additional_rate_limits"),
    )


def _window(value: Any) -> QuotaWindow | None:
    if not isinstance(value, dict):
        return None
    return QuotaWindow(
        used=_int_or_none(value.get("used")),
        limit=_int_or_none(value.get("limit")),
        remaining=_int_or_none(value.get("remaining")),
        resets_at=_str_or_none(
            value.get("resets_at")
            or value.get("reset_at")
            or value.get("reset_after")
            or value.get("reset_after_seconds")
        ),
        raw=value,
    )


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)
