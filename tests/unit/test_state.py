"""Unit tests for daily-run cooldown state."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from luckflow.config import settings
from luckflow.storage import state


@pytest.fixture
def temp_state(tmp_path, monkeypatch):
    target = tmp_path / "state" / "last_daily_run.json"
    monkeypatch.setattr(type(settings), "daily_run_state_file", property(lambda self: target))
    return target


def test_cooldown_disabled_always_allows(monkeypatch, temp_state):
    monkeypatch.setattr(settings.daily, "cooldown_enabled", False)
    assert state.can_run_daily() == (True, 0.0)


def test_cooldown_first_run_allows(monkeypatch, temp_state):
    monkeypatch.setattr(settings.daily, "cooldown_enabled", True)
    assert state.get_last_run() is None
    allowed, remaining = state.can_run_daily()
    assert allowed is True and remaining == 0.0


def test_cooldown_blocks_within_interval(monkeypatch, temp_state):
    monkeypatch.setattr(settings.daily, "cooldown_enabled", True)
    monkeypatch.setattr(settings.daily, "interval_hours", 24)
    temp_state.parent.mkdir(parents=True, exist_ok=True)
    recent = (datetime.now() - timedelta(hours=1)).isoformat()
    temp_state.write_text(json.dumps({"last_run": recent}), encoding="utf-8")
    allowed, remaining = state.can_run_daily()
    assert allowed is False
    assert remaining > 0


def test_format_time_remaining():
    assert state.format_time_remaining(3661) == "1h 1m 1s"
