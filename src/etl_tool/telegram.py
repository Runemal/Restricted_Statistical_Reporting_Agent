from __future__ import annotations

from html import escape
import os

import httpx

from .config import TelegramConfig


def send_telegram_message(config: TelegramConfig, text: str) -> bool:
    if not config.enabled:
        return False

    token = os.environ.get(config.bot_token_env)
    chat_id = os.environ.get(config.chat_id_env)
    if not token or not chat_id:
        raise RuntimeError(
            f"Telegram env vars are required: {config.bot_token_env}, {config.chat_id_env}"
        )

    url = f"{config.api_base_url.rstrip('/')}/bot{token}/sendMessage"
    with httpx.Client(timeout=20) as client:
        response = client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": render_telegram_html(text)[:3900],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Telegram sendMessage failed with HTTP {exc.response.status_code}"
            ) from exc
    return True


def render_telegram_html(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            lines.append(f"<b>{escape(heading)}</b>")
        else:
            lines.append(escape(line))
    return "\n".join(lines)
