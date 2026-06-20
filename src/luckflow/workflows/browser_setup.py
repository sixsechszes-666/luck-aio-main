"""Browser-setup workflow: import the wallet seed and configure the captcha solver.

Ported from ``process_single_browser_setup`` / ``prepare_browser`` in ``luck_main.py``.
"""

from __future__ import annotations

import asyncio

from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.wallet_setup import setup_captcha, setup_wallet
from luckflow.storage import load_accounts, save_statistics


class BrowserSetupWorkflow(Workflow):
    """Set up each profile's wallet (from its seed) and captcha extension."""

    name = "Browser & Wallet Setup"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.data_dir / "data.xlsx")

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "result_setup.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        result = AccountResult.new(f"Setup-{index + 1:03d}")
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link

        seed_phrase = account.get("SEED_PHRASE")
        if not seed_phrase or str(seed_phrase).lower() in ("nan", "none", ""):
            log.warning(f"Skipping account {index + 1}: no SEED_PHRASE")
            result.RESULT = "SKIPPED_NO_SEED_PHRASE"
            return result
        seed_phrase = str(seed_phrase).strip()

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}", "Setup...")
        try:
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            log.success(f"✓ Browser launched for ID {account.profile_id}")
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            log.info("💳 Setting up wallet...")
            await setup_wallet(page, seed_phrase)
            log.info("🤖 Configuring captcha...")
            await setup_captcha(page)
            await asyncio.sleep(1)
            result.RESULT = ResultStatus.SUCCESS.value
            log.success(f"✅ Account {index + 1} set up")
        except Exception as exc:  # noqa: BLE001
            log.error(f"Setup error for account {index + 1}", str(exc)[:50])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"ID:{account.profile_id}")
        return result


async def run_browser_setup(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await BrowserSetupWorkflow(workers or settings.concurrency.max_workers).run()
