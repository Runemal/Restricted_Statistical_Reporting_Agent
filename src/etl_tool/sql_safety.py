from __future__ import annotations

import re
import sqlite3

DESTRUCTIVE_SQL = re.compile(
    r"\b(attach|alter|create|delete|detach|drop|insert|pragma\s+writable_schema|"
    r"reindex|replace|truncate|update|vacuum)\b",
    re.IGNORECASE,
)

ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE | re.DOTALL)


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            statement = candidate.rstrip(";").strip()
            if statement:
                statements.append(statement)
            buffer = []
    trailing = "\n".join(buffer).strip()
    if trailing:
        statements.append(trailing.rstrip(";").strip())
    return statements


def assert_read_only_sql(statement: str) -> None:
    cleaned = _strip_leading_comments(statement).strip()
    if not ALLOWED_START.search(cleaned):
        raise ValueError("Only SELECT or WITH statements are allowed")
    if DESTRUCTIVE_SQL.search(cleaned):
        raise ValueError("Destructive SQL keyword detected")


def _strip_leading_comments(statement: str) -> str:
    text = statement.lstrip()
    while text.startswith("--"):
        _, _, text = text.partition("\n")
        text = text.lstrip()
    return text

