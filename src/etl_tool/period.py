from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import ReportPeriod


def current_report_period() -> ReportPeriod:
    timezone_name = os.environ.get("REPORT_TIMEZONE", "Europe/Moscow")
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    start = datetime.combine(today, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return ReportPeriod(
        label=f"{today.isoformat()} ({timezone_name})",
        since_utc=_as_utc_text(start),
        until_utc=_as_utc_text(end),
    )


def resolve_period_path(path: str, period: ReportPeriod) -> str:
    return (
        path.replace("{since_utc}", period.since_utc)
        .replace("{until_utc}", period.until_utc)
        .replace("{report_date}", period.label)
    )


def _as_utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
