"""Public-URL tunnels for exposing the local dashboard.

A compact replacement for the legacy ``result/*_tunnel.py`` collection: a single
serveo.net (SSH reverse-tunnel) implementation plus the shared helpers the
dashboard launcher used (``ensure_secret_token`` / ``notify_tunnel_url``).
serveo needs only an SSH client — no account or extra binary.
"""

from __future__ import annotations

import re
import secrets
import subprocess
import threading
from collections.abc import Callable

from luckflow.config import settings
from luckflow.config.settings import PROJECT_ROOT
from luckflow.core import logging as log

_TOKEN_FILE = PROJECT_ROOT / "data" / "state" / "dashboard_token.txt"
_SERVEO_URL_RE = re.compile(r"https://[\w-]+\.serveo\.net")


def ensure_secret_token() -> str:
    """Return a stable dashboard secret token, generating one on first use."""
    if settings.server.dashboard_secret_token:
        return settings.server.dashboard_secret_token
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(18)
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def notify_tunnel_url(url: str, token: str) -> bool:
    """Send the public URL + token to Telegram (no-op if Telegram is unset)."""
    from luckflow.notifications.telegram import send_message

    return send_message(f"🌐 LuckFlow dashboard\nURL: {url}\nToken: <code>{token}</code>")


def start_tunnel_with_watchdog(
    port: int, on_reconnect: Callable[[str], None] | None = None
) -> str | None:
    """Open a serveo.net reverse tunnel to ``localhost:port`` and return its URL.

    A background watchdog thread restarts the tunnel if it drops, invoking
    ``on_reconnect`` with the new URL.
    """
    if not settings.server.tunnel_enabled:
        log.info("ℹ️  Tunnel disabled")
        return None

    def _spawn() -> tuple[subprocess.Popen, str | None]:
        proc = subprocess.Popen(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{port}", "serveo.net"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        url = None
        for _ in range(30):
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                break
            match = _SERVEO_URL_RE.search(line)
            if match:
                url = match.group(0)
                break
        return proc, url

    try:
        proc, url = _spawn()
    except FileNotFoundError:
        log.warning("⚠️  ssh client not found — cannot start serveo tunnel")
        return None
    if not url:
        log.warning("⚠️  Could not obtain serveo URL")
        return None

    def _watchdog(process: subprocess.Popen) -> None:
        process.wait()
        if not settings.server.tunnel_enabled:
            return
        log.warning("Tunnel dropped, reconnecting...")
        new_proc, new_url = _spawn()
        if new_url and on_reconnect:
            on_reconnect(new_url)
        threading.Thread(target=_watchdog, args=(new_proc,), daemon=True).start()

    threading.Thread(target=_watchdog, args=(proc,), daemon=True).start()
    return url


__all__ = ["ensure_secret_token", "notify_tunnel_url", "start_tunnel_with_watchdog"]
