"""Pure, side-effect-free helpers (proxy parsing, balance math).

These were buried in ``luck_core.py`` next to logging and Playwright calls.
Pulled out here they are trivially unit-testable (see ``tests/unit``).
"""

from __future__ import annotations

import re
from typing import Any

ProxyConfig = dict[str, str]

_NULLISH = {"", "nan", "none", "null"}


def parse_proxy(value: Any) -> ProxyConfig | None:
    """Parse ``host:port[:user:pass]`` into a Playwright proxy dict.

    Returns ``None`` for empty/invalid input instead of raising, so a missing
    proxy degrades to a direct connection.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NULLISH:
        return None

    parts = text.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return {"server": f"http://{host}:{port}", "username": user, "password": password}
    if len(parts) == 2:
        host, port = parts
        return {"server": f"http://{host}:{port}"}
    return None


def extract_balance_number(text: Any) -> float:
    """Extract the first ``$1,234.56`` style amount from a string as a float."""
    if not text:
        return 0.0
    match = re.search(r"\$([\d,.]+)", str(text))
    if not match:
        return 0.0
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return 0.0


def _to_float(balance: Any) -> float:
    """Best-effort conversion of a localized balance string to float."""
    try:
        return float(str(balance).replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def calculate_balance_difference(start: Any, end: Any, deposit: float = 0.0) -> str:
    """Return a signed ``+$x.xx`` / ``-$x.xx`` delta, accounting for deposits."""
    diff = _to_float(end) - _to_float(start) - deposit
    if diff > 0:
        return f"+${diff:.2f}"
    if diff < 0:
        return f"-${abs(diff):.2f}"
    return "$0.00"


def balance_decreased(previous: str, current: str, *, enabled: bool = True) -> bool:
    """True if ``current`` balance is strictly lower than ``previous``."""
    if not enabled:
        return False
    try:
        prev = float(str(previous).replace(" ", "").replace(",", ""))
        curr = float(str(current).replace(" ", "").replace(",", ""))
    except ValueError:
        return False
    return curr < prev
