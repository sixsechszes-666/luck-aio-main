"""Extension-fix workflow: clear profile cache, then re-import the Solflare seed.

Ported from ``process_single_account_extension_fix``. For each profile in
``data_for_fix.xlsx``: clear its ixBrowser cache, launch the browser, re-import
the wallet from its ``SEED_PHRASE`` column, and close.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_profile_cache,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.wallet_setup import setup_wallet
from luckflow.storage import load_accounts, save_statistics


class ExtensionFixWorkflow(Workflow):
    """Clear cache and re-import the wallet seed for each profile."""

    name = "Extension Fix"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_extension_fix)

    def _result_path(self) -> Path:
        return settings.result_dir / "result_extension_fix.xlsx"

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, self._result_path())

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Worker-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link

        seed_phrase = account.get("SEED_PHRASE")
        if not seed_phrase or str(seed_phrase).lower() in ("nan", "none", ""):
            log.step(worker_id, "⚠️ ", "No SEED_PHRASE — skipping")
            result.RESULT = "SKIPPED_NO_SEED_PHRASE"
            return result
        seed_phrase = str(seed_phrase).strip()

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")
        try:
            log.step(worker_id, "🧹", f"Clearing cache for profile {account.profile_id}...")
            await clear_profile_cache(account.profile_id, worker_id)

            log.step(worker_id, "🚀", "Launching browser...")
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            log.step(worker_id, "✓ ", "Browser launched")

            log.step(worker_id, "💳", "Importing seed phrase...")
            await setup_wallet(page, seed_phrase)
            log.step(worker_id, "✓ ", "Seed phrase imported")

            await asyncio.sleep(2)
            result.RESULT = ResultStatus.SUCCESS.value
            log.step(worker_id, "✅", "Done")
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Error", str(exc)[:80])
            result.RESULT = f"ERROR: {str(exc)[:80]}"
        finally:
            await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
        return result


async def run_extension_fix(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await ExtensionFixWorkflow(workers or settings.concurrency.max_workers).run()
