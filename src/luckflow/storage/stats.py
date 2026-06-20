"""Statistics persistence (Excel) and summary printing.

Ported from ``luck_statistics.py``. Adds a small :class:`StatsWriter` so
workflows can checkpoint results to a configured path without hard-coding it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from luckflow.core import logging as log
from luckflow.core.models import AccountResult


def _rows(results: list[AccountResult] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r.to_dict() if isinstance(r, AccountResult) else r for r in results]


def save_statistics(
    results: list[AccountResult] | list[dict[str, Any]],
    path: str | Path,
    *,
    append: bool = False,
) -> None:
    """Write results to ``path`` as ``.xlsx``, optionally appending to existing rows."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df_new = pd.DataFrame(_rows(results))

        if append and path.exists():
            try:
                df_existing = pd.read_excel(path, dtype=str).astype(str)
                df_combined = pd.concat([df_existing, df_new.astype(str)], ignore_index=True)
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not read existing stats file, overwriting", str(exc))
                df_combined = df_new
        else:
            df_combined = df_new

        df_combined.to_excel(path, index=False, engine="openpyxl")
        log.success("💾 Statistics saved", str(path))
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to save statistics", str(exc))


class StatsWriter:
    """Bind a results file once; checkpoint to it repeatedly."""

    def __init__(self, path: str | Path, *, append: bool = False) -> None:
        self.path = Path(path)
        self.append = append

    def __call__(self, results: list[AccountResult]) -> None:
        save_statistics(results, self.path, append=self.append)
