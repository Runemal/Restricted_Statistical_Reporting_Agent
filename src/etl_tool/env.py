from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def find_env_file(start: str | Path | None = None) -> Path | None:
    current = Path(start or ".").resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.exists():
            return candidate
    return None


def load_env_file(path: str | Path | None = None) -> None:
    env_path = Path(path) if path is not None else find_env_file()
    if env_path is None or not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not _ENV_NAME_RE.match(key) or key in os.environ:
            continue

        os.environ[key] = _parse_env_value(value.strip())


def expand_env_refs(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: expand_env_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env_refs(item) for item in value]
    if isinstance(value, str):
        return _expand_string(value)
    return value


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _expand_string(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        fallback = match.group(2)
        env_value = os.environ.get(name)
        if env_value:
            return env_value
        if fallback is not None:
            return fallback
        raise ValueError(f"Missing required environment variable: {name}")

    return _ENV_REF_RE.sub(replace, value)
