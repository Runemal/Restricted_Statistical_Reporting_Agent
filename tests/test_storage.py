from pathlib import Path

import pytest

from etl_tool.storage import run_query_file, write_rows


def test_write_rows_and_read_only_queries(tmp_path: Path):
    saved = write_rows(
        [{"id": 1, "status": "ok"}, {"id": 2, "status": "failed"}],
        tmp_path,
        "daily_report",
    )
    query_file = tmp_path / "report.sql"
    query_file.write_text(
        "SELECT COUNT(*) AS row_count FROM daily_report;\n"
        "SELECT status FROM daily_report ORDER BY id;\n",
        encoding="utf-8",
    )

    results = run_query_file(saved.sqlite_path, query_file)

    assert saved.csv_path.exists()
    assert saved.sqlite_path.exists()
    assert results[0].rows_preview == [{"row_count": 2}]
    assert results[1].rows_preview == [{"status": "ok"}, {"status": "failed"}]


def test_query_file_rejects_delete(tmp_path: Path):
    saved = write_rows([{"id": 1}], tmp_path, "daily_report")
    query_file = tmp_path / "report.sql"
    query_file.write_text("DELETE FROM daily_report;", encoding="utf-8")

    with pytest.raises(ValueError):
        run_query_file(saved.sqlite_path, query_file)

