"""Standalone Renew Play Timer workflow.

Ported from ``luck_renew.py``. For each account: open the site, connect the
wallet, and if the "Renew Play Timer" button is present, fund it via a forward
chain, click renew, confirm in the wallet, then reverse the funds back to Main.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

import base58
from solders.keypair import Keypair

from luckflow.blockchain.solana import forward_transaction_chain, reverse_transaction_chain
from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.browser.session import safe_click
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.connect import connect_wallet, connect_wallet_withdraw
from luckflow.storage import load_accounts, save_statistics


def _rpc_url() -> str:
    return settings.solana.helius_rpc_url or settings.solana.rpc_url


def _wallets_log_path() -> Path:
    return settings.data_dir / "logs" / "wallets.log"


class RenewWorkflow(Workflow):
    """Detect and renew the play timer for each funded account."""

    name = "Renew Play Timer"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_registration)

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "result_renew.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Worker-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link

        main_pk = account.get("PRIVATE_KEY_MAIN")
        master_pk = account.get("PRIVATE_KEY_MASTER")
        worker_pk = account.get("PRIVATE_KEY_WORKER")
        if not main_pk or not master_pk or not worker_pk:
            log.warning(f"[{worker_id}] Skipping: missing private keys")
            result.RESULT = "SKIPPED_NO_KEYS"
            return result
        target_address = account.wallet_address

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")
        try:
            log.step(worker_id, "🎯", "Launching browser...")
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            for _ in range(3):
                try:
                    await page.goto(account.link)
                    break
                except Exception:  # noqa: BLE001
                    continue
            try:
                await connect_wallet(page)
            except Exception:  # noqa: BLE001
                await connect_wallet_withdraw(page)

            context = page.context
            await asyncio.sleep(10)

            button = await page.query_selector("button.css-1ex6wv0")
            if not button or (await button.inner_text()).strip() != "Renew Play Timer":
                log.warning(f"[{worker_id}] Renew button not found")
                result.RESULT = "BUTTON_NOT_FOUND"
                return result

            log.success(f"[{worker_id}] Renew button found")
            if target_address:
                amount = random.uniform(settings.funding.registration_min, settings.funding.registration_max)
                forward_result = await forward_transaction_chain(
                    rpc_url=_rpc_url(), main_private_key=main_pk, master_private_key=master_pk,
                    worker_address=target_address, row_id=account.profile_id, log_file=_wallets_log_path(),
                    num_temp_wallets=settings.solana.num_temp_wallets, amount_in_sol=amount,
                    wait_timeout=settings.solana.transaction_timeout, use_master=settings.solana.use_master_wallet,
                )
                if forward_result["status"] != "success":
                    result.extra["FORWARD_TRANSACTION_STATUS"] = "failed"
                    result.RESULT = "FORWARD_FAILED"
                    return result
                result.extra["FORWARD_TRANSACTION_STATUS"] = "success"
                await asyncio.sleep(15)

            await safe_click(page.locator('button.css-1ex6wv0:has-text("Renew Play Timer")'))
            await asyncio.sleep(1)
            await safe_click(
                page.locator('button.css-1ex6wv0[style*="width: 100%"]:has-text("Renew Play Timer")')
            )

            try:
                connection_page = await context.wait_for_event("page", timeout=50_000)
                await connection_page.wait_for_load_state("domcontentloaded")
                try:
                    await connection_page.locator('button:has-text("I trust this site")').click(timeout=3000)
                except Exception:  # noqa: BLE001
                    pass
                await connection_page.bring_to_front()
                await connection_page.click("button.btn-primary")
            except Exception as confirm_exc:  # noqa: BLE001
                log.warning(f"[{worker_id}] Confirm warning: {confirm_exc}")

            await asyncio.sleep(10)
            main_address = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())
            reverse_result = await reverse_transaction_chain(
                rpc_url=_rpc_url(), worker_private_key=worker_pk, master_private_key=master_pk,
                main_address=main_address, row_id=account.profile_id, log_file=_wallets_log_path(),
                num_temp_wallets=settings.solana.num_temp_wallets,
                wait_timeout=settings.solana.transaction_timeout, use_master=settings.solana.use_master_wallet,
            )
            result.extra["REVERSE_TRANSACTION_STATUS"] = reverse_result["status"]
            await asyncio.sleep(3)
            result.RESULT = ResultStatus.SUCCESS.value
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Runtime error", str(exc)[:50])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
        return result


async def run_renew(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await RenewWorkflow(workers or settings.concurrency.max_timer_check).run()
