from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from .env import expand_env_refs, find_env_file, load_env_file


class SshConfig(BaseModel):
    target: str
    port: int = 22
    identity_file: str | None = None
    local_host: str = "127.0.0.1"
    local_port: int = 18080
    remote_host: str = "127.0.0.1"
    remote_port: int
    connect_timeout_seconds: int = 20


class ApiConfig(BaseModel):
    path: str
    timeout_seconds: int = 30
    headers: dict[str, str] = Field(default_factory=dict)
    data_path: str | None = None

    @field_validator("path")
    @classmethod
    def validate_relative_http_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("api.path must start with '/'")
        if "://" in value:
            raise ValueError("api.path must be a path, not an absolute URL")
        return value


class StorageConfig(BaseModel):
    output_dir: Path = Path("./out")
    dataset_name: str = "dataset"

    @field_validator("dataset_name")
    @classmethod
    def validate_dataset_name(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("dataset_name may contain only letters, numbers, and underscores")
        return value


class TelegramConfig(BaseModel):
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "TELEGRAM_CHAT_ID"
    api_base_url: str = "https://api.telegram.org"
    enabled: bool = True


class PipelineConfig(BaseModel):
    ssh: SshConfig
    api: ApiConfig
    storage: StorageConfig = Field(default_factory=StorageConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


def load_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path)
    load_env_file(find_env_file(config_path.parent))
    with config_path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}
    return PipelineConfig.model_validate(expand_env_refs(raw))
