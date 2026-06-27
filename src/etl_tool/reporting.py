from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .models import PipelineRunResult, QueryResult, QuotaInfo, QuotaWindow, ReportPeriod


def build_summary(
    extracted_rows: int,
    query_results: list[QueryResult],
    period: ReportPeriod | None = None,
    quota: QuotaInfo | None = None,
) -> str:
    hourly = _rows(query_results, "query_1")
    users = _rows(query_results, "query_2")
    anomalies = _rows(query_results, "query_3")

    aggregate_rows = hourly or users
    total_requests = sum(_int(row.get("requests")) for row in aggregate_rows) or extracted_rows
    total_tokens = sum(_int(row.get("total_tokens")) for row in aggregate_rows)
    input_tokens = sum(_int(row.get("input_tokens")) for row in aggregate_rows)
    output_tokens = sum(_int(row.get("output_tokens")) for row in aggregate_rows)
    reasoning_tokens = sum(_int(row.get("reasoning_tokens")) for row in aggregate_rows)
    cached_tokens = sum(_int(row.get("cached_tokens")) for row in aggregate_rows)
    failed_requests = sum(_int(row.get("failed_requests")) for row in aggregate_rows)
    avg_latency = _weighted_average(aggregate_rows, "avg_latency_ms", "requests")
    cache_share = 100.0 * cached_tokens / input_tokens if input_tokens else 0.0

    lines = [
        *_quota_lines(quota),
        "",
        f"#Сводка по использованию за день: {period.label if period else 'текущий день'}",
        "",
        f"#Всего событий: {_fmt_int(extracted_rows)}.",
        (
            f"Запросы: {_fmt_int(total_requests)}, токены: {_fmt_int(total_tokens)} "
            f"(input {_fmt_int(input_tokens)}, output {_fmt_int(output_tokens)})."
        ),
        f"Reasoning tokens: {_fmt_int(reasoning_tokens)}, cached tokens: {_fmt_int(cached_tokens)} ({cache_share:.1f}% от input).",
        f"Ошибки: {_fmt_int(failed_requests)} ({_pct(failed_requests, total_requests):.2f}%).",
    ]

    if avg_latency is not None:
        lines.append(f"Средняя latency: {avg_latency:.0f} мс.")

    if hourly:
        peak_by_tokens = max(hourly, key=lambda row: _int(row.get("total_tokens")))
        peak_by_requests = max(hourly, key=lambda row: _int(row.get("requests")))
        slowest_hour = max(hourly, key=lambda row: _float(row.get("avg_latency_ms")))
        lines.extend(
            [
                "",
                "#Динамика по часам:",
                (
                    f"Пик по токенам: {_hour(peak_by_tokens)} — "
                    f"{_fmt_int(_int(peak_by_tokens.get('total_tokens')))} токенов."
                ),
                (
                    f"Пик по запросам: {_hour(peak_by_requests)} — "
                    f"{_fmt_int(_int(peak_by_requests.get('requests')))} запросов."
                ),
                (
                    f"Самая высокая средняя latency: {_hour(slowest_hour)} — "
                    f"{_float(slowest_hour.get('avg_latency_ms')):.0f} мс."
                ),
            ]
        )

    if users:
        lines.append("")
        lines.append("#Пользователи:")
        for row in users[:5]:
            lines.append(
                f"{row.get('username', 'unknown')} ({row.get('team', 'unknown')}): "
                f"{_fmt_int(_int(row.get('requests')))} запросов, "
                f"{_fmt_int(_int(row.get('total_tokens')))} токенов, "
                f"errors {_fmt_int(_int(row.get('failed_requests')))}, "
                f"avg latency {_float(row.get('avg_latency_ms')):.0f} мс."
            )

    lines.append("")
    if anomalies:
        lines.append("#Аномалии: есть пользователи выше порога 100M токенов/час:")
        for row in anomalies[:5]:
            lines.append(
                f"{_hour(row)} {row.get('username', 'unknown')} ({row.get('team', 'unknown')}): "
                f"{_fmt_int(_int(row.get('total_tokens')))} токенов."
            )
    else:
        lines.append("#Аномалии: пользователей выше порога 100M токенов/час не найдено.")

    return "\n".join(lines)


def telegram_message(result: PipelineRunResult) -> str:
    if result.status == "ok":
        parts = [result.summary]
    else:
        parts = ["Сбор статистики CLIProxyAPI не выполнен."]
    if result.error:
        parts.append(f"Ошибка: {result.error}")
    return "\n".join(part for part in parts if part)


def _rows(query_results: list[QueryResult], name: str) -> list[dict[str, Any]]:
    for result in query_results:
        if result.name == name:
            return result.rows_preview
    return []


def _int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float | None:
    total_weight = sum(_int(row.get(weight_key)) for row in rows)
    if not total_weight:
        return None
    weighted_sum = sum(_float(row.get(value_key)) * _int(row.get(weight_key)) for row in rows)
    return weighted_sum / total_weight


def _pct(part: int, total: int) -> float:
    return 100.0 * part / total if total else 0.0


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _hour(row: dict[str, Any]) -> str:
    value = str(row.get("hour", "unknown"))
    if not value.endswith("Z"):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        timezone_name = os.environ.get("REPORT_TIMEZONE", "Europe/Moscow")
        local = parsed.astimezone(ZoneInfo(timezone_name))
        return f"{local.strftime('%H:00')} ({timezone_name})"
    except Exception:
        return value


def _quota_lines(quota: QuotaInfo | None) -> list[str]:
    lines = ["#Лимиты Codex/ChatGPT:"]
    if quota is None:
        return [*lines, "не проверялись."]
    if quota.error:
        return [*lines, quota.error]

    if quota.plan_type:
        lines.append(f"План: {quota.plan_type.capitalize()}.")
    window_5h = _quota_window_line("#5h", quota.code_5h)
    if window_5h:
        lines.append(window_5h)
    window_7d = _quota_window_line("#7d", quota.code_7d)
    if window_7d:
        lines.append(window_7d)

    additional = _additional_limits_lines(quota.additional_rate_limits)
    if additional:
        lines.extend(additional)
    if len(lines) == 1:
        lines.append("данные по лимитам в ответе отсутствуют.")
    return lines


def _quota_window_line(label: str, window: QuotaWindow | None) -> str | None:
    if window is None:
        return None
    parts = []
    used_percent = _raw_int(window, "used_percent")
    if used_percent is not None:
        parts.append(f"использовано {used_percent}%")
    if window.used is not None:
        parts.append(f"использовано {_fmt_int(window.used)}")
    if window.limit is not None:
        parts.append(f"лимит {_fmt_int(window.limit)}")
    if window.remaining is not None:
        parts.append(f"осталось {_fmt_int(window.remaining)}")
    reset_after = _raw_int(window, "reset_after_seconds")
    if reset_after is not None:
        parts.append(f"сброс через {_fmt_duration(reset_after)}")
    elif window.resets_at:
        parts.append(f"сброс {window.resets_at}")
    if not parts:
        return None
    return f"{label}: " + ", ".join(parts) + "."


def _additional_limits_lines(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        lines = ["Дополнительные лимиты:"]
        for item in value[:5]:
            if not isinstance(item, dict):
                lines.append(_short(item))
                continue
            name = item.get("limit_name") or item.get("metered_feature") or "unknown"
            rate_limit = item.get("rate_limit") if isinstance(item.get("rate_limit"), dict) else {}
            allowed = rate_limit.get("allowed")
            reached = rate_limit.get("limit_reached")
            primary = _window_from_dict(rate_limit.get("primary_window"))
            secondary = _window_from_dict(rate_limit.get("secondary_window"))
            status = []
            if allowed is not None:
                status.append("доступен" if allowed else "недоступен")
            if reached is not None:
                status.append("лимит достигнут" if reached else "лимит не достигнут")
            details = ", ".join(status) if status else "без статуса"
            lines.append(f"{name}: {details}.")
            primary_line = _quota_window_line("5h", primary)
            if primary_line:
                lines.append(primary_line)
            secondary_line = _quota_window_line("7d", secondary)
            if secondary_line:
                lines.append(secondary_line)
        return lines
    if isinstance(value, dict):
        items = list(value.items())[:3]
        return ["Дополнительные лимиты:"] + [f"{key}: {_short(item)}" for key, item in items]
    return ["Дополнительные лимиты: " + _short(value)]


def _short(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 180 else text[:177] + "..."


def _window_from_dict(value: Any) -> QuotaWindow | None:
    if not isinstance(value, dict):
        return None
    return QuotaWindow(raw=value)


def _raw_int(window: QuotaWindow, key: str) -> int | None:
    if not window.raw:
        return None
    value = window.raw.get(key)
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}с"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}м"
    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours}ч {minutes}м"
    days = hours // 24
    hours = hours % 24
    return f"{days}д {hours}ч"
