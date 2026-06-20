"""The :class:`Workflow` template that every operating mode implements.

Each of the original 12 menu modes (daily, registration, withdraw, renew, ...)
boiled down to: *load a spreadsheet → process each row with bounded concurrency →
save stats → print a summary*. That control flow now lives here **once**; a
concrete workflow only supplies ``load_accounts`` and ``process_account``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, WorkflowSummary
from luckflow.core.runner import WorkerPool


class Workflow(ABC):
    """Base class for an account-processing workflow."""

    #: Human-readable name, shown in logs and the dashboard.
    name: str = "workflow"

    def __init__(self, concurrency: int, *, checkpoint_every: int = 5) -> None:
        self.concurrency = concurrency
        self._checkpoint_every = checkpoint_every

    # --- To be implemented by subclasses ---------------------------------
    @abstractmethod
    def load_accounts(self) -> list[Account]:
        """Read and validate the input spreadsheet into typed accounts."""

    @abstractmethod
    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        """Process a single account. Must not raise for expected failures."""

    # --- Optional hooks ---------------------------------------------------
    def save_results(self, results: list[AccountResult]) -> None:
        """Persist (partial) results. Override to write Excel/JSON."""

    def summarize(self, results: list[AccountResult]) -> WorkflowSummary:
        summary = WorkflowSummary.from_results(results)
        log.header(f"📊 {self.name.upper()} — SUMMARY")
        log.detail("Total accounts", str(summary.total))
        log.detail("✅ Succeeded", str(summary.succeeded))
        log.detail("❌ Failed", str(summary.failed))
        log.separator("═")
        return summary

    # --- Template method --------------------------------------------------
    async def run(self) -> WorkflowSummary:
        """Load → process concurrently → checkpoint → summarize."""
        log.header(f"▶️  {self.name.upper()}")
        accounts = self.load_accounts()

        def _checkpoint(results: list[AccountResult]) -> None:
            self.save_results(results)
            log.info("💾 Checkpoint saved", f"{len(results)} results")

        pool: WorkerPool[Account, AccountResult] = WorkerPool(
            self.concurrency,
            checkpoint=_checkpoint,
            checkpoint_every=self._checkpoint_every,
        )
        raw = await pool.run(accounts, self.process_account)

        # Normalise: handler exceptions become ERROR results (defensive).
        results: list[AccountResult] = []
        for item, res in zip(accounts, raw, strict=False):
            if isinstance(res, AccountResult):
                results.append(res)
            else:
                fallback = AccountResult.new("Worker-???")
                fallback.UD_DIR = item.user_data_dir
                fallback.RESULT = f"RUNTIME_ERROR: {str(res)[:50]}"
                results.append(fallback)

        self.save_results(results)
        return self.summarize(results)
