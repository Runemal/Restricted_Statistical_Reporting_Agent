from pathlib import Path

from etl_tool.config import load_config


def test_config_expands_env_refs_from_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("TEST_ETL_SSH_TARGET", raising=False)
    monkeypatch.delenv("TEST_ETL_REMOTE_PORT", raising=False)

    (tmp_path / ".env").write_text(
        "TEST_ETL_SSH_TARGET=etl-user@test-host\n"
        "TEST_ETL_REMOTE_PORT=8090\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
ssh:
  target: "${TEST_ETL_SSH_TARGET}"
  remote_port: "${TEST_ETL_REMOTE_PORT}"
api:
  path: "/reports"
storage:
  dataset_name: "daily_report"
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.ssh.target == "etl-user@test-host"
    assert config.ssh.remote_port == 8090


def test_existing_environment_wins_over_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_ETL_SSH_TARGET", "etl-user@shell-host")
    (tmp_path / ".env").write_text("TEST_ETL_SSH_TARGET=etl-user@file-host\n", encoding="utf-8")
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
ssh:
  target: "${TEST_ETL_SSH_TARGET}"
  remote_port: 8080
api:
  path: "/reports"
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.ssh.target == "etl-user@shell-host"
