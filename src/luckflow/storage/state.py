"""Daily-run cooldown state.

Consolidates the cooldown helpers that lived in the legacy ``main.py``
(``save_last_run_time`` / ``get_last_run_time`` / ``can_run_daily_tasks``).
The last-run timestamp is persisted as JSON under the configured data dir.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from luckflow.config import settings
from luckflow.core import logging as log


def save_last_run(offset_minutes: int = 10) -> None:
    """Persist ``now + offset_minutes`` as the last daily-run time."""
    path = settings.daily_run_state_file
    path.parent.mkdir(parents=True, exist_ok=True)
    adjusted = datetime.now() + timedelta(minutes=offset_minutes)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"last_run": adjusted.isoformat()}, fh)
    log.info("📅 Last run time saved", f"+{offset_minutes} min")


def get_last_run() -> datetime | None:
    """Return the last daily-run time, or ``None`` if never run."""
    path = settings.daily_run_state_file
    try:
        with open(path, encoding="utf-8") as fh:
            return datetime.fromisoformat(json.load(fh)["last_run"])
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Error reading last-run time", str(exc))
        return None


def can_run_daily() -> tuple[bool, float]:
    """Return ``(allowed, remaining_seconds)`` based on the configured cooldown."""
    if not settings.daily.cooldown_enabled:
        return True, 0.0

    last_run = get_last_run()
    if last_run is None:
        return True, 0.0

    hours_passed = (datetime.now() - last_run).total_seconds() / 3600
    interval = settings.daily.interval_hours
    if hours_passed >= interval:
        return True, 0.0
    return False, (interval - hours_passed) * 3600


def format_time_remaining(seconds: float) -> str:
    """Format a duration as ``Hh Mm Ss``."""
    seconds = int(seconds)
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m {seconds % 60}s"
