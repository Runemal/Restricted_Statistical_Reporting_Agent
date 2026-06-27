from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import QueryResult, SavedFiles
from .sql_safety import assert_read_only_sql, split_sql_statements


def write_rows(rows: list[dict[str, Any]], output_dir: Path, dataset_name: str) -> SavedFiles:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{dataset_name}.csv"
    sqlite_path = output_dir / f"{dataset_name}.sqlite"
    columns = _columns_for(rows)

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{dataset_name}"')
        column_sql = ", ".join(f'"{column}" TEXT' for column in columns)
        conn.execute(f'CREATE TABLE "{dataset_name}" ({column_sql})')
        if rows:
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f'INSERT INTO "{dataset_name}" VALUES ({placeholders})',
                [[_sqlite_value(row.get(column)) for column in columns] for row in rows],
            )
        conn.commit()

    return SavedFiles(csv_path=csv_path, sqlite_path=sqlite_path)


def run_query_file(sqlite_path: Path, sql_path: Path, preview_limit: int = 100) -> list[QueryResult]:
    sql_text = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    results: list[QueryResult] = []
    uri = f"file:{sqlite_path.resolve()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        for index, statement in enumerate(statements, start=1):
            assert_read_only_sql(statement)
            cursor = conn.execute(statement)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description or []]
            preview = [
                {column: row[column] for column in columns}
                for row in rows[:preview_limit]
            ]
            results.append(
                QueryResult(
                    name=f"query_{index}",
                    sql=statement,
                    row_count=len(rows),
                    columns=columns,
                    rows_preview=preview,
                )
            )
    return results


def _columns_for(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            column = str(key)
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return columns or ["empty_result"]


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _sqlite_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
