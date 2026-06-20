"""Background task manager driving workflows for the dashboard.

A single :class:`TaskManager` runs one workflow at a time in a dedicated thread
(with its own asyncio loop), tracks live status, and captures log lines via
:class:`~luckflow.core.logging.LogHub`. The dashboard polls :meth:`status`.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from luckflow.core import logging as log

# Map dashboard task identifiers → workflow coroutine factories.
_TASK_REGISTRY: dict[str, tuple[str, Callable[[int | None], Awaitable[Any]]]] = {}


def _register() -> None:
    from luckflow.workflows import (
        collect_profile_list,
        run_browser_setup,
        run_daily,
        run_extension_fix,
        run_hardware_login,
        run_manual_withdraw,
        run_registration,
        run_renew,
        run_warmup_registration,
        run_warmup_volume,
        run_withdraw,
        run_worker_sweep,
    )

    _TASK_REGISTRY.update(
        {
            "daily": ("Daily Tasks", run_daily),
            "warmup_volume_bonuses": ("Warmup Volume Bonuses", run_warmup_volume),
            "extension_fix": ("Extension Fix", run_extension_fix),
            "registration": ("Registration", lambda w: run_registration()),
            "warmup_registration": ("Warmup Registration", run_warmup_registration),
            "withdraw": ("Withdraw Balances", run_withdraw),
            "renew": ("Renew Play Timer", run_renew),
            "browser_setup": ("Browser Setup", run_browser_setup),
            "hardware_login": ("Hardware Login", run_hardware_login),
            "manual_withdraw": ("Manual Withdraw", run_manual_withdraw),
            "profile_list": ("Profile List", lambda w: collect_profile_list()),
            "worker_sweep": ("Worker Sweep", run_worker_sweep),
        }
    )


class TaskManager:
    """Owns the lifecycle and status of the currently running workflow."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.reset()
        log.LogHub.subscribe(self._capture_log)

    def reset(self) -> None:
        self.status_value = "idle"
        self.task_type: str | None = None
        self.task_name: str | None = None
        self.workers = 0
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.error: str | None = None
        self.log: list[str] = []
        self.errors: list[str] = []
        self.wait_remaining = 0

    # --- logging sink ----------------------------------------------------
    def _capture_log(self, message: str) -> None:
        if self.status_value not in ("running", "waiting"):
            return
        self.log.append(message)
        if len(self.log) > 1000:
            self.log = self.log[-1000:]
        lowered = message.lower()
        if "error" in lowered or "❌" in message:
            self.errors.append(message)

    # --- control ---------------------------------------------------------
    def start(self, task_type: str, workers: int, wait_seconds: float = 0) -> dict:
        with self._lock:
            if self.status_value in ("running", "waiting"):
                return {"ok": False, "error": "A task is already running"}
            if not _TASK_REGISTRY:
                _register()  # lazily import workflows (and their heavy deps)
            if task_type not in _TASK_REGISTRY:
                return {"ok": False, "error": f"Unknown task type: {task_type}"}

            self.reset()
            self.task_type = task_type
            self.task_name, factory = _TASK_REGISTRY[task_type]
            self.workers = workers
            self.status_value = "waiting" if wait_seconds > 0 else "running"
            self.started_at = time.time()
            self.wait_remaining = int(wait_seconds)

            self._thread = threading.Thread(
                target=self._run, args=(factory, workers, wait_seconds), daemon=True
            )
            self._thread.start()
            return {"ok": True}

    def _run(self, factory, workers: int, wait_seconds: float) -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            if wait_seconds > 0:
                end = time.time() + wait_seconds
                while time.time() < end and self.status_value == "waiting":
                    self.wait_remaining = max(0, int(end - time.time()))
                    time.sleep(1)
                self.status_value = "running"
            self._loop.run_until_complete(factory(workers))
            self.status_value = "completed"
        except Exception as exc:  # noqa: BLE001
            self.status_value = "error"
            self.error = str(exc)
            log.error("Task failed", str(exc))
        finally:
            self.finished_at = time.time()
            self._loop.close()

    def stop(self) -> dict:
        with self._lock:
            if self.status_value not in ("running", "waiting"):
                return {"ok": False, "error": "No task is running"}
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            self.status_value = "idle"
            self.finished_at = time.time()
            return {"ok": True}

    def status(self) -> dict:
        elapsed = None
        if self.started_at:
            end = self.finished_at or time.time()
            elapsed = round(end - self.started_at, 1)
        from luckflow.storage import can_run_daily

        _, cooldown_remaining = can_run_daily()
        return {
            "status": self.status_value,
            "task_type": self.task_type,
            "task_name": self.task_name,
            "workers": self.workers,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed": elapsed,
            "error": self.error,
            "log": self.log[-300:],
            "errors": self.errors[-100:],
            "progress_current": 0,
            "progress_total": 0,
            "wait_remaining": self.wait_remaining,
            "cooldown_remaining": int(cooldown_remaining),
        }


task_manager = TaskManager()
