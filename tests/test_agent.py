from types import SimpleNamespace

from etl_tool.agent import _AgentRunState


def test_agent_state_builds_fallback_report_after_telegram_send():
    state = _AgentRunState()
    state.observe(
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    content=[
                        {
                            "type": "text",
                            "text": (
                                '{"status":"ok","checkpoints":[],"saved_files":null,'
                                '"extracted_rows":7,"query_results":[{"name":"query_1",'
                                '"sql":"SELECT 1","row_count":0,"columns":[],"rows_preview":[]}],'
                                '"summary":"Фактическая сводка","telegram_sent":false}'
                            ),
                        }
                    ]
                )
            ]
        )
    )
    state.observe(
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    name="mcp__restricted_etl__send_telegram_report",
                    input={"intro": "Ироничное вступление."},
                )
            ]
        )
    )
    state.observe(
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    content=[
                        {
                            "type": "text",
                            "text": '{"telegram_sent": true, "summary": "Ироничное вступление.\\n\\nФактическая сводка"}',
                        }
                    ]
                )
            ]
        )
    )

    report = state.to_report()

    assert report is not None
    assert report.status == "ok"
    assert report.extracted_rows == 7
    assert report.query_result_count == 1
    assert report.summary.startswith("Ироничное вступление.")
    assert report.telegram_sent is True
