"""Account registration workflow.

Ported from ``luck_registration.py``. For each account: fund the target wallet
through a forward temp-wallet chain, launch the browser, connect the wallet,
activate the account, then (after the browser closes) return remaining SOL via a
reverse chain. Runs sequentially, mirroring the original.
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
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.connect import connect_wallet_registration, prepare_account
from luckflow.storage import load_accounts, save_statistics


def _rpc_url() -> str:
    return settings.solana.helius_rpc_url or settings.solana.rpc_url


def _wallets_log_path() -> Path:
    return settings.data_dir / "logs" / "wallets.log"


class RegistrationWorkflow(Workflow):
    """Register/activate new accounts, funding and de-funding them on-chain."""

    name = "Registration"

    def __init__(self) -> None:
        super().__init__(concurrency=1)  # registration is inherently sequential

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_registration, require_wallet=True)

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "registration_result.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"REG-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link
        result.extra["WALLET_ADDRESS"] = account.wallet_address

        main_pk = account.get("PRIVATE_KEY_MAIN") or None
        master_pk = account.get("PRIVATE_KEY_MASTER")
        worker_pk = account.get("PRIVATE_KEY_WORKER")
        if not master_pk or not worker_pk:
            result.RESULT = "SKIPPED_MISSING_KEYS"
            return result

        playwright = browser = page = client = None
        forward_completed = False
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")
        try:
            log.info(f"[{worker_id}] Profile", account.user_data_dir)
            if main_pk:
                amount = round(random.uniform(settings.funding.min_amount, settings.funding.max_amount), 4)
                log.info(f"[{worker_id}] Funding amount", f"{amount} SOL")
                forward_result = await forward_transaction_chain(
                    rpc_url=_rpc_url(), main_private_key=main_pk, master_private_key=master_pk,
                    worker_address=account.wallet_address, row_id=account.profile_id,
                    log_file=_wallets_log_path(), num_temp_wallets=settings.solana.num_temp_wallets,
                    amount_in_sol=amount, wait_timeout=settings.solana.transaction_timeout,
                    use_master=settings.solana.use_master_wallet,
                )
                result.extra["FORWARD_TRANSACTION_STATUS"] = forward_result["status"]
                result.extra["SOL_SENT"] = forward_result.get("amount_sent")
                if forward_result["status"] != "success":
                    result.RESULT = "TRANSACTION_FAILED"
                    return result
                forward_completed = True
            else:
                log.warning(f"[{worker_id}] No main key — skipping forward chain")
                result.extra["FORWARD_TRANSACTION_STATUS"] = "skipped"

            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            await page.goto(account.link)
            log.info(f"[{worker_id}] Connecting wallet")
            await connect_wallet_registration(page)
            log.info(f"[{worker_id}] Preparing account")
            await prepare_account(page)
            log.success(f"[{worker_id}] Registration completed")
            result.RESULT = ResultStatus.SUCCESS.value
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Critical error", str(exc)[:100])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            try:
                await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
            except Exception as exc:  # noqa: BLE001
                log.error(f"[{worker_id}] Cleanup error", str(exc))
            await asyncio.sleep(20)
            if main_pk and forward_completed:
                await self._return_funds(worker_id, account, main_pk, master_pk, worker_pk, result)
            elif main_pk and not forward_completed:
                result.extra["REVERSE_TRANSACTION_STATUS"] = "skipped"
        return result

    async def _return_funds(self, worker_id, account, main_pk, master_pk, worker_pk, result) -> None:
        try:
            log.info(f"[{worker_id}] Returning remaining SOL")
            main_address = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())
            reverse_result = await reverse_transaction_chain(
                rpc_url=_rpc_url(), worker_private_key=worker_pk, master_private_key=master_pk,
                main_address=main_address, row_id=account.profile_id, log_file=_wallets_log_path(),
                num_temp_wallets=settings.solana.num_temp_wallets,
                wait_timeout=settings.solana.transaction_timeout, use_master=settings.solana.use_master_wallet,
            )
            result.extra["REVERSE_TRANSACTION_STATUS"] = reverse_result["status"] if reverse_result else "failed"
            await asyncio.sleep(15)
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Reverse chain error", str(exc))
            result.extra["REVERSE_TRANSACTION_STATUS"] = "failed"


async def run_registration() -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await RegistrationWorkflow().run()
