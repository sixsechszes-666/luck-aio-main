"""Telegram notifications.

A lightweight wrapper over the Telegram Bot API. If no token is configured the
functions degrade to no-ops (with a warning) instead of failing — so the rest of
the system never depends on Telegram being set up.

Ported/simplified from ``telegram_bot.py``: the original also offered remote
command polling to launch the dashboard; the clean version focuses on outbound
notifications, which is the part the rest of the app relies on.
"""

from __future__ import annotations

import requests

from luckflow.config import settings
from luckflow.core import logging as log


def is_configured() -> bool:
    return bool(settings.telegram.bot_token and settings.telegram.user_id)


def send_message(text: str) -> bool:
    """Send a message to the configured Telegram user. Returns success."""
    if not is_configured():
        log.warning("Telegram not configured — message not sent")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.telegram.bot_token}/sendMessage",
            json={"chat_id": settings.telegram.user_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return response.ok
    except Exception as exc:  # noqa: BLE001
        log.warning("Telegram send error", str(exc))
        return False


def start_telegram_bot() -> None:
    """Hook kept for parity with the CLI entrypoint; warns if unconfigured."""
    if not is_configured():
        log.warning("⚠️  Telegram bot token not set — notifications disabled")
        return
    log.info("📨 Telegram notifications enabled")
