"""Typed domain models shared across workflows.

The original project passed around bare ``dict`` "account_stats" objects with
stringly-typed keys (``'UD_DIR'``, ``'RESULT'`` ...). :class:`AccountResult`
keeps the **exact same wire format** (via :meth:`to_dict`) so the Excel exporter
and React dashboard keep working, while giving the Python code real attributes,
defaults and IDE support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ResultStatus(str, Enum):
    """Canonical outcomes for processing a single account."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    AUTH_FAILED = "AUTH_FAILED"
    CHEST_UNAVAILABLE = "CHEST_UNAVAILABLE"
    CHEST_CRITICAL_ERROR = "CHEST_CRITICAL_ERROR"
    RENEW_CRITICAL_ERROR = "RENEW_CRITICAL_ERROR"
    SKIPPED_NO_UD_DIR = "SKIPPED_NO_UD_DIR"
    SKIPPED_NO_LINK = "SKIPPED_NO_LINK"
    SKIPPED_NO_WALLET = "SKIPPED_NO_WALLET"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"


@dataclass(slots=True)
class Account:
    """A single account/profile row read from the operator's spreadsheet."""

    profile_id: int
    user_data_dir: str
    link: str
    wallet_address: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style access to the original spreadsheet row (parity helper)."""
        return self.raw.get(key, default)


@dataclass
class AccountResult:
    """Per-account statistics. Field names mirror the legacy stats dict keys."""

    WORKER_ID: str
    UD_DIR: Any = None
    LINK: Any = None
    START_BALANCE: Any = None
    END_BALANCE: Any = None
    BALANCE_DIFFERENCE: Any = None
    START_SOL_BALANCE: Any = None
    END_SOL_BALANCE: Any = None
    SOL_BALANCE_DIFFERENCE: Any = None
    DODEP_SOL: float = 0.0
    DODEP_USD: float = 0.0
    RESULT: str = ResultStatus.ERROR.value
    LOGIN_LINK: Any = None
    EXTERNAL_WALLET: Any = None
    CHEST_AMOUNT: float = 0.0
    WITHDRAW_RESULT: str = ""
    WITHDRAW_AMOUNT: float = 0
    WITHDRAW_DATE: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Flatten to the legacy dict shape consumed by Excel/dashboard."""
        data = asdict(self)
        extra = data.pop("extra")
        data.update(extra)
        return data

    @classmethod
    def new(cls, worker_id: str) -> AccountResult:
        return cls(WORKER_ID=worker_id)


@dataclass
class WorkflowSummary:
    """Aggregate outcome of a workflow run."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[AccountResult] = field(default_factory=list)

    @classmethod
    def from_results(cls, results: list[AccountResult]) -> WorkflowSummary:
        succeeded = sum(1 for r in results if ResultStatus.SUCCESS.value == r.RESULT)
        return cls(
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )
