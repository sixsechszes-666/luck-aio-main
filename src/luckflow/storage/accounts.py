"""Read account spreadsheets into validated :class:`Account` objects.

Replaces the per-row validation that ``account_handler.py`` performed by mutating
a stats dict and appending to a shared list. Here loading and validation are a
pure transformation ``path -> list[Account]``; invalid rows are logged and
skipped, never silently mixed into results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from luckflow.core import logging as log
from luckflow.core.models import Account

_NULLISH = {"", "nan", "none", "null"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _NULLISH else text


def validate_account(row: pd.Series, *, require_wallet: bool = False) -> Account | None:
    """Validate one spreadsheet row. Returns ``None`` (and logs) if unusable."""
    user_data_dir = _clean(row.get("UD_DIR"))
    link = _clean(row.get("LINK"))

    if not user_data_dir:
        log.warning("Skipping row: missing UD_DIR")
        return None
    if not link:
        log.warning("Skipping row: missing LINK", f"UD_DIR={user_data_dir}")
        return None

    try:
        profile_id = int(user_data_dir)
    except ValueError:
        log.warning("Skipping row: UD_DIR is not an integer", user_data_dir)
        return None

    wallet = _clean(row.get("WALLET_ADDRESS"))
    if require_wallet and not wallet:
        log.warning("Skipping row: missing WALLET_ADDRESS", f"UD_DIR={user_data_dir}")
        return None

    return Account(
        profile_id=profile_id,
        user_data_dir=user_data_dir,
        link=link,
        wallet_address=wallet,
        raw=row.to_dict(),
    )


def load_accounts(path: str | Path, *, require_wallet: bool = False) -> list[Account]:
    """Load and validate all accounts from an ``.xlsx`` file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Account spreadsheet not found: {path}")

    frame = pd.read_excel(path)
    accounts: list[Account] = []
    for _, row in frame.iterrows():
        account = validate_account(row, require_wallet=require_wallet)
        if account is not None:
            accounts.append(account)

    log.info("📂 Loaded accounts", f"{len(accounts)}/{len(frame)} valid from {path.name}")
    return accounts
