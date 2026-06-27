from pathlib import Path

import pytest

from etl_tool.tools import _assert_bound_path, compose_final_message


def test_compose_final_message_keeps_summary_immutable():
    summary = "#Лимиты:\nПлан: Pro."

    message = compose_final_message("  #Шутка по фактам.\n\nЛишняя строка\nЕще лишняя  ", summary)

    assert message == "Шутка по фактам.\nЛишняя строка\n\n#Лимиты:\nПлан: Pro."


def test_bound_path_rejects_unexpected_path(tmp_path: Path):
    expected = tmp_path / "pipeline.yaml"
    actual = tmp_path / "other.yaml"
    expected.write_text("ok", encoding="utf-8")
    actual.write_text("no", encoding="utf-8")

    with pytest.raises(ValueError, match="config_path is fixed"):
        _assert_bound_path(actual, expected.resolve(), "config_path")
