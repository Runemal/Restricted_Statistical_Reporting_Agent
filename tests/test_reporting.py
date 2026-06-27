from pathlib import Path

from etl_tool.models import PipelineRunResult, QueryResult, QuotaInfo, QuotaWindow, ReportPeriod, SavedFiles
from etl_tool.reporting import build_summary, telegram_message


def test_build_summary_is_russian_analytics():
    summary = build_summary(
        3,
        [
            QueryResult(
                name="query_1",
                sql="SELECT 1",
                row_count=2,
                columns=[],
                rows_preview=[
                    {
                        "hour": "2026-06-27T10:00:00Z",
                        "requests": 1,
                        "total_tokens": 100,
                        "input_tokens": 80,
                        "output_tokens": 20,
                        "reasoning_tokens": 5,
                        "cached_tokens": 40,
                        "failed_requests": 0,
                        "avg_latency_ms": 1000,
                    },
                    {
                        "hour": "2026-06-27T11:00:00Z",
                        "requests": 2,
                        "total_tokens": 500,
                        "input_tokens": 450,
                        "output_tokens": 50,
                        "reasoning_tokens": 10,
                        "cached_tokens": 100,
                        "failed_requests": 1,
                        "avg_latency_ms": 2000,
                    },
                ],
            ),
            QueryResult(
                name="query_2",
                sql="SELECT 2",
                row_count=1,
                columns=[],
                rows_preview=[
                    {
                        "username": "alice",
                        "team": "de",
                        "requests": 3,
                        "total_tokens": 600,
                        "failed_requests": 1,
                        "avg_latency_ms": 1666.67,
                    }
                ],
            ),
            QueryResult(name="query_3", sql="SELECT 3", row_count=0, columns=[], rows_preview=[]),
        ],
        ReportPeriod(
            label="2026-06-27 (Europe/Moscow)",
            since_utc="2026-06-26T21:00:00Z",
            until_utc="2026-06-27T21:00:00Z",
        ),
        QuotaInfo(
            status_code=200,
            plan_type="plus",
            allowed=True,
            code_5h=QuotaWindow(used=10, limit=100, remaining=90),
            code_7d=QuotaWindow(used=20, limit=1000, remaining=980),
        ),
    )

    assert summary.startswith("#Лимиты Codex/ChatGPT:")
    assert "План: Plus." in summary
    assert "#5h: использовано 10, лимит 100, осталось 90." in summary
    assert "#Сводка по использованию за день: 2026-06-27 (Europe/Moscow)" in summary
    assert "#Всего событий: 3." in summary
    assert "токены: 600" in summary
    assert "Ошибки: 1 (33.33%)." in summary
    assert "Пик по токенам: 14:00 (Europe/Moscow) — 500 токенов." in summary
    assert "alice (de): 3 запросов" in summary


def test_telegram_message_omits_saved_file_paths():
    message = telegram_message(
        PipelineRunResult(
            status="ok",
            saved_files=SavedFiles(csv_path=Path("out/data.csv"), sqlite_path=Path("out/data.sqlite")),
            summary="Русская аналитическая сводка",
        )
    )

    assert message == "Русская аналитическая сводка"
    assert "CSV" not in message
    assert "SQLite" not in message
