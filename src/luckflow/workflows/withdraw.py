"""Standalone batch-withdraw workflow.

Ported from ``luck_withdraw.process_single_withdrawal`` + ``withdraw_balances``.
For each account: authenticate, and if the balance exceeds the configured
threshold, fund the worker (forward chain), transfer funds out via the UI,
unwrap wSOL, then reverse remaining funds back to Main.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

import base58
from solders.keypair import Keypair

from luckflow.blockchain.solana import (
    forward_transaction_chain,
    reverse_transaction_chain,
    wait_and_unwrap_wsol,
    wait_for_stable_balance,
)
from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.auth import authenticate_and_get_balance
from luckflow.platform.balance import get_sol_balance
from luckflow.platform.connect import wallet_connect_session
from luckflow.platform.withdraw import withdraw_balance_luck
from luckflow.storage import load_accounts, save_statistics


def _rpc_url() -> str:
    return settings.solana.helius_rpc_url or settings.solana.rpc_url


def _wallets_log_path() -> Path:
    return settings.data_dir / "logs" / "wallets.log"


class WithdrawWorkflow(Workflow):
    """Withdraw balances above a threshold, keeping a small random reserve."""

    name = "Withdraw Balances"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_withdraw, require_wallet=True)

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "result_withdraw.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Withdraw-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link
        result.extra["WALLET_ADDRESS"] = account.wallet_address

        cfg = settings.withdraw
        main_pk = account.get("PRIVATE_KEY_MAIN")
        master_pk = account.get("PRIVATE_KEY_MASTER")
        worker_pk = account.get("PRIVATE_KEY_WORKER")

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")
        try:
            log.step(worker_id, "🎯", "Launching browser...")
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            try:
                start_balance, auth_success = await authenticate_and_get_balance(page, account.link, worker_id)
                if not auth_success or start_balance is None:
                    result.RESULT = ResultStatus.AUTH_FAILED.value
                    return result
                try:
                    usd_balance = float(str(start_balance).replace(",", "."))
                except (ValueError, TypeError):
                    usd_balance = 0.0
                result.START_BALANCE = usd_balance
                log.info(f"💰 [{worker_id}] Start balance: ${usd_balance:.4f}")

                start_sol = await get_sol_balance(page, worker_id)
                if start_sol is not None:
                    result.START_SOL_BALANCE = start_sol

                try:
                    await page.locator("button.css-1wc7o8w:has-text('Do Nothing')").click(timeout=3000)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    await wallet_connect_session(page)
                except Exception as exc:  # noqa: BLE001
                    log.warning(f"[{worker_id}] wallet_connect_session: {exc}")

                if usd_balance < cfg.min_balance_to_start:
                    log.warning(f"[{worker_id}] Balance ${usd_balance:.4f} < ${cfg.min_balance_to_start:.2f} — skip")
                    result.RESULT = "SKIPPED_LOW_BALANCE"
                    result.extra["WITHDRAWAL_STATUS"] = "SKIPPED_LOW_BALANCE"
                    return result

                keep_amount = round(random.uniform(cfg.keep_min, cfg.keep_max), 4)
                withdraw_amount = usd_balance - keep_amount
                sol_price = usd_balance / start_sol if start_sol and start_sol > 0 else 180.0
                amount_to_keep_sol = keep_amount / sol_price
                log.info(f"📊 [{worker_id}] Keeping ${keep_amount:.4f} (~{amount_to_keep_sol:.6f} SOL)")

                forward_completed = await self._forward(worker_id, account, main_pk, master_pk, worker_pk)
                await asyncio.sleep(random.uniform(5, 8))
                await withdraw_balance_luck(page, amount_to_keep_sol=amount_to_keep_sol)
                await asyncio.sleep(3)

                if worker_pk:
                    await self._unwrap(worker_id, worker_pk)
                if forward_completed:
                    await self._reverse(worker_id, account, main_pk, master_pk, worker_pk)

                result.RESULT = ResultStatus.SUCCESS.value
                result.extra["WITHDRAWAL_STATUS"] = f"WITHDREW_APPROX_{withdraw_amount:.4f}"
            except Exception as exc:  # noqa: BLE001
                log.error(f"[{worker_id}] Withdrawal error", str(exc)[:80])
                result.RESULT = f"WITHDRAWAL_ERROR: {str(exc)[:50]}"
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Runtime error", str(exc)[:80])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
        return result

    async def _forward(self, worker_id, account, main_pk, master_pk, worker_pk) -> bool:
        if not (main_pk and master_pk and worker_pk):
            log.warning(f"[{worker_id}] Missing keys for forward transfer")
            return False
        try:
            worker_address = str(Keypair.from_bytes(base58.b58decode(worker_pk)).pubkey())
            amount = round(random.uniform(0.015, 0.025), 4)
            log.info(f"🔄 [{worker_id}] Forward transfer ({amount} SOL)...")
            res = await forward_transaction_chain(
                rpc_url=_rpc_url(), main_private_key=main_pk, master_private_key=master_pk,
                worker_address=worker_address, row_id=account.profile_id, log_file=_wallets_log_path(),
                num_temp_wallets=settings.solana.num_temp_wallets, amount_in_sol=amount,
                wait_timeout=300, use_master=settings.solana.use_master_wallet,
            )
            if res.get("status") == "success":
                log.success(f"✅ [{worker_id}] Forward transfer succeeded")
                return True
            log.error(f"❌ [{worker_id}] Forward transfer error: {res.get('error')}")
            return False
        except Exception as exc:  # noqa: BLE001
            log.error(f"❌ [{worker_id}] Forward transfer exception", str(exc))
            return False

    async def _unwrap(self, worker_id, worker_pk) -> None:
        try:
            log.info(f"🔄 [{worker_id}] Unwrapping wSOL...")
            sig = await wait_and_unwrap_wsol(
                rpc_url=_rpc_url(), owner_private_key_b58=worker_pk, wait_for_funds=True, timeout=300
            )
            log.success(f"✅ [{worker_id}] wSOL unwrapped (sig: {sig})")
            address = str(Keypair.from_bytes(base58.b58decode(worker_pk)).pubkey())
            await wait_for_stable_balance(rpc_url=_rpc_url(), address=address, poll_interval=0.3, stable_reads=2, timeout=30)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"[{worker_id}] wSOL unwrap error (may be absent): {exc}")

    async def _reverse(self, worker_id, account, main_pk, master_pk, worker_pk) -> None:
        try:
            main_address = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())
            log.info(f"🔄 [{worker_id}] Reverse transfer...")
            res = await reverse_transaction_chain(
                rpc_url=_rpc_url(), worker_private_key=worker_pk, master_private_key=master_pk,
                main_address=main_address, row_id=account.profile_id, log_file=_wallets_log_path(),
                num_temp_wallets=settings.solana.num_temp_wallets, wait_timeout=300,
                use_master=settings.solana.use_master_wallet,
            )
            if res.get("status") == "success":
                log.success(f"✅ [{worker_id}] Reverse transfer succeeded")
            else:
                log.error(f"❌ [{worker_id}] Reverse transfer error: {res.get('error')}")
        except Exception as exc:  # noqa: BLE001
            log.error(f"❌ [{worker_id}] Reverse transfer exception", str(exc))


async def run_withdraw(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await WithdrawWorkflow(workers or settings.concurrency.max_withdraw).run()
