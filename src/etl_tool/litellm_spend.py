from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx

from .env import load_env_file


def fetch_spend_logs(base_url: str, master_key: str, limit: int = 50) -> Any:
    headers = {"Authorization": f"Bearer {master_key}"}
    params = {"limit": limit}
    with httpx.Client(timeout=20) as client:
        response = client.get(
            f"{base_url.rstrip('/')}/spend/logs",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch LiteLLM /spend/logs.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000"),
    )
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()
    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if not master_key:
        raise SystemExit("LITELLM_MASTER_KEY is required")
    logs = fetch_spend_logs(args.base_url, master_key, args.limit)
    print(json.dumps(logs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
