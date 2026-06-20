"""Warmup-registration workflow.

Ported from ``luck_warmup_registration.py``. Like registration but browser-only
(no on-chain funding): connect the wallet then run the bonus pre-activation
(``warm_up``). Accounts are processed in a random order.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.connect import connect_wallet_registration, warm_up
from luckflow.storage import load_accounts, save_statistics


class WarmupRegistrationWorkflow(Workflow):
    """Connect the wallet and pre-activate weekly/monthly bonuses for each account."""

    name = "Warmup Registration"

    def load_accounts(self) -> list[Account]:
        accounts = load_accounts(settings.excel_warmup_registration, require_wallet=True)
        random.shuffle(accounts)
        return accounts

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "warmup_registration" / "result_warmup_registration.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"REG-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link
        result.extra["WALLET_ADDRESS"] = account.wallet_address

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}", "Warmup Reg...")
        try:
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            await page.goto(account.link)
            log.info(f"[{worker_id}] Connecting wallet")
            await connect_wallet_registration(page)

            log.info(f"[{worker_id}] Preparing account")
            await asyncio.sleep(random.uniform(1, 3))
            await page.locator("div.css-ylk4v3").click()
            await warm_up(page)

            log.success(f"[{worker_id}] Warmup registration completed")
            result.RESULT = ResultStatus.SUCCESS.value
            result.extra["COMPLETED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Critical error", str(exc)[:100])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            try:
                await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
            except Exception as exc:  # noqa: BLE001
                log.error(f"[{worker_id}] Cleanup error", str(exc))
        return result


async def run_warmup_registration(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await WarmupRegistrationWorkflow(workers or settings.concurrency.max_workers).run()
