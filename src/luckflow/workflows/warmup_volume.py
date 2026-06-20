"""Warmup-Volume workflow: play 10–15 rounds across modes with on-chain top-ups.

Ported from ``process_single_account_warmup_volume_bonuses`` + the
``complete_warmup_volume_bonuses`` orchestrator. Differs from the daily workflow:
authenticates with the registration connect flow, uses the volume game engine and
the volume chest claim, and accounts for top-up (dodep) amounts in the balance delta.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.utils import calculate_balance_difference
from luckflow.core.workflow import Workflow
from luckflow.platform.auth import authenticate_and_get_balance
from luckflow.platform.balance import (
    get_chest_status,
    get_external_wallet,
    get_link_for_login,
    get_sol_balance,
    process_final_balance,
)
from luckflow.platform.chest import process_chest_volume
from luckflow.platform.connect import connect_wallet_registration, wallet_connect_session
from luckflow.platform.games import execute_game_logic_volumes
from luckflow.platform.renew import check_and_renew_playtimer
from luckflow.storage import load_accounts, save_statistics


class WarmupVolumeWorkflow(Workflow):
    """Generate trading volume across all four games, topping up funds as needed."""

    name = "Warmup Volume Bonuses"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_daily)

    def _result_path(self) -> Path:
        return settings.result_dir / "result_warmup_volume_bonuses.xlsx"

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, self._result_path())

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Worker-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link

        playwright = browser = page = client = None
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")

        try:
            log.step(worker_id, "🎯", "Launching browser...")
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            log.step(worker_id, "✓ ", "Browser launched")
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception as exc:  # noqa: BLE001
                log.step(worker_id, "⚠️ ", "clear_pages error", str(exc))

            try:
                log.step(worker_id, "🌐", f"Navigating to {account.link[:30]}...")
                start_balance, auth_success = await authenticate_and_get_balance(
                    page, account.link, worker_id, connect=connect_wallet_registration
                )
                if not auth_success or start_balance is None:
                    log.step(worker_id, "❌", "Could not read balance after auth")
                    result.RESULT = ResultStatus.AUTH_FAILED.value
                    return result
                result.START_BALANCE = start_balance

                start_sol = await get_sol_balance(page, worker_id)
                if start_sol is not None:
                    result.START_SOL_BALANCE = start_sol

                await self._gather_links(page, worker_id, result)

                log.step(worker_id, "⏰", "Checking Renew Play Timer...")
                context = browser.contexts[0] if browser and browser.contexts else None
                if await check_and_renew_playtimer(page, account, worker_id, context) is False:
                    log.step(worker_id, "❌", "Critical renew error. Aborting.")
                    result.RESULT = ResultStatus.RENEW_CRITICAL_ERROR.value
                    return result

                log.step(worker_id, "🎮", "Starting volume game...")
                await execute_game_logic_volumes(page, result, index, account)

                if not await self._handle_chest(page, worker_id, result, start_balance):
                    return result

                end_balance, end_sol, sol_diff = await process_final_balance(
                    page, account.link, worker_id, result.to_dict()
                )
                result.END_BALANCE = end_balance
                result.BALANCE_DIFFERENCE = calculate_balance_difference(
                    start_balance, end_balance, result.DODEP_USD or 0.0
                )
                if end_sol is not None:
                    result.END_SOL_BALANCE = end_sol
                if sol_diff is not None:
                    result.SOL_BALANCE_DIFFERENCE = sol_diff - (result.DODEP_SOL or 0.0)

                log.step(worker_id, "✅", f"Done | ${end_balance} | {result.BALANCE_DIFFERENCE}")
                result.RESULT = ResultStatus.SUCCESS.value
            except Exception as exc:  # noqa: BLE001
                log.error(f"[{worker_id}] Game error", str(exc)[:80])
                result.RESULT = f"GAME_ERROR: {str(exc)[:50]}"
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Runtime error", str(exc)[:80])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
        finally:
            await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
        return result

    async def _gather_links(self, page, worker_id: str, result: AccountResult) -> None:
        steps = [
            (get_link_for_login, "LOGIN_LINK", "Login link fetched"),
            (get_external_wallet, "EXTERNAL_WALLET", "Internal wallet"),
            (wallet_connect_session, "WALLET_CONNECTED", "Wallet connected (saved session)"),
        ]
        random.shuffle(steps)
        for func, key, success_msg in steps:
            value = await func(page)
            if value:
                if key == "LOGIN_LINK":
                    result.LOGIN_LINK = value
                elif key == "EXTERNAL_WALLET":
                    result.EXTERNAL_WALLET = value
                else:
                    result.extra[key] = value
                log.step(worker_id, "🔗", success_msg, f"{str(value)[:50]}...")
            else:
                log.step(worker_id, "⚠️ ", f"Failed to fetch {key}")
                raise RuntimeError(f"Failed to fetch {key}")
        await asyncio.sleep(1)

    async def _handle_chest(self, page, worker_id: str, result: AccountResult, start_balance) -> bool:
        log.step(worker_id, "📦", "Checking chest...")
        chest_status = await get_chest_status(page)
        if chest_status == "unavailable":
            log.step(worker_id, "❌", "Chest unavailable")
            self._freeze_balances(result, start_balance)
            result.RESULT = ResultStatus.CHEST_UNAVAILABLE.value
            return False
        if chest_status == "available":
            log.step(worker_id, "🎁", "Processing chest...")
            try:
                await process_chest_volume(page, worker_id)
            except Exception as chest_error:  # noqa: BLE001
                log.step(worker_id, "🚫", "Chest error", str(chest_error))
                self._freeze_balances(result, start_balance)
                result.RESULT = ResultStatus.CHEST_CRITICAL_ERROR.value
                return False
        elif chest_status == "not_found":
            log.step(worker_id, "⚠️ ", "Chest not found")
        return True

    @staticmethod
    def _freeze_balances(result: AccountResult, start_balance) -> None:
        result.END_BALANCE = start_balance
        result.END_SOL_BALANCE = result.START_SOL_BALANCE
        if result.START_SOL_BALANCE is not None:
            result.SOL_BALANCE_DIFFERENCE = 0.0
        result.BALANCE_DIFFERENCE = 0.0


async def run_warmup_volume(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await WarmupVolumeWorkflow(workers or settings.concurrency.max_workers).run()
