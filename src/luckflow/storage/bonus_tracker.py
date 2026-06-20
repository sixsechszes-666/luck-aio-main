"""Track when weekly/monthly bonuses were last claimed, per account.

Ported from ``projects/bonus_tracker.py``. State is stored as JSON under the
configured data dir. Countdown strings are now English.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from luckflow.config import settings

WEEKLY_INTERVAL_DAYS = 7
MONTHLY_INTERVAL_DAYS = 30


def _tracker_file() -> Path:
    return settings.data_dir / "bonus_tracker.json"


def _load_all() -> dict:
    import json

    path = _tracker_file()
    try:
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save_all(data: dict) -> None:
    import json

    path = _tracker_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        print(f"[bonus_tracker] save error: {exc}")


def load_bonus_info(ud_dir: str) -> dict:
    """Return ``{'weekly_claimed_at', 'monthly_claimed_at'}`` for one account."""
    account_data = _load_all().get(str(ud_dir), {})
    return {
        "weekly_claimed_at": account_data.get("weekly_claimed_at"),
        "monthly_claimed_at": account_data.get("monthly_claimed_at"),
    }


def save_bonus_info(ud_dir: str, weekly_claimed: bool = False, monthly_claimed: bool = False) -> None:
    """Record a claim timestamp for whichever bonus was just claimed."""
    if not weekly_claimed and not monthly_claimed:
        return
    all_data = _load_all()
    account_data = all_data.setdefault(str(ud_dir), {})
    now_str = datetime.now().isoformat()
    if weekly_claimed:
        account_data["weekly_claimed_at"] = now_str
    if monthly_claimed:
        account_data["monthly_claimed_at"] = now_str
    _save_all(all_data)


def format_countdown(claimed_at_str: str | None, interval_days: int) -> str:
    """Human-readable time until the next claim (e.g. ``in 6d 12h``)."""
    if not claimed_at_str:
        return "no data"
    try:
        next_available = datetime.fromisoformat(claimed_at_str) + timedelta(days=interval_days)
        delta = next_available - datetime.now()
        if delta.total_seconds() <= 0:
            return "available now!"
        total = int(delta.total_seconds())
        days, hours, minutes = total // 86400, (total % 86400) // 3600, (total % 3600) // 60
        if days > 0:
            return f"in {days}d {hours}h"
        if hours > 0:
            return f"in {hours}h {minutes}m"
        return f"in {minutes}m"
    except Exception:  # noqa: BLE001
        return "no data"


def _next_available_iso(claimed_at_str: str | None, days: int) -> str | None:
    if not claimed_at_str:
        return None
    try:
        return (datetime.fromisoformat(claimed_at_str) + timedelta(days=days)).isoformat()
    except Exception:  # noqa: BLE001
        return None


def get_bonus_status_for_account(ud_dir: str) -> dict:
    """Full bonus status for one account (for the dashboard and logs)."""
    info = load_bonus_info(ud_dir)
    weekly_at, monthly_at = info["weekly_claimed_at"], info["monthly_claimed_at"]
    return {
        "weekly_claimed_at": weekly_at,
        "monthly_claimed_at": monthly_at,
        "weekly_countdown": format_countdown(weekly_at, WEEKLY_INTERVAL_DAYS),
        "monthly_countdown": format_countdown(monthly_at, MONTHLY_INTERVAL_DAYS),
        "next_weekly_at": _next_available_iso(weekly_at, WEEKLY_INTERVAL_DAYS),
        "next_monthly_at": _next_available_iso(monthly_at, MONTHLY_INTERVAL_DAYS),
    }


def get_all_bonus_statuses() -> dict:
    """Bonus status for every tracked account (used by the dashboard)."""
    return {ud_dir: get_bonus_status_for_account(ud_dir) for ud_dir in _load_all()}
