import pytest

from etl_tool.sql_safety import assert_read_only_sql, split_sql_statements


def test_allows_select_and_with():
    assert_read_only_sql("SELECT 1")
    assert_read_only_sql("WITH rows AS (SELECT 1 AS value) SELECT * FROM rows")


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM x",
        "SELECT 1; DROP TABLE x",
        "WITH x AS (DELETE FROM y RETURNING *) SELECT * FROM x",
        "UPDATE x SET a = 1",
    ],
)
def test_blocks_destructive_sql(statement):
    with pytest.raises(ValueError):
        assert_read_only_sql(statement)


def test_splits_sql_statements():
    statements = split_sql_statements("SELECT 1;\n\nSELECT 2;")
    assert statements == ["SELECT 1", "SELECT 2"]

