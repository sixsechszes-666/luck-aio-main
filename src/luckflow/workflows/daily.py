"""Daily-tasks workflow: authenticate, claim chest, play a game, settle balance.

Ported from ``luck_daily.process_single_account`` + the ``complete_daily``
orchestrator in ``luck_main.py``, restructured as a :class:`Workflow`. The
``WorkerPool`` owns concurrency and checkpointing, so this class only describes
*what one account does*.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
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
from luckflow.platform.chest import process_chest
from luckflow.platform.connect import wallet_connect_session
from luckflow.platform.games import execute_game_logic
from luckflow.platform.renew import check_and_renew_playtimer
from luckflow.platform.withdraw import get_trigger, try_withdraw_in_daily
from luckflow.storage import load_accounts, save_statistics
from luckflow.storage.bonus_tracker import (
    MONTHLY_INTERVAL_DAYS,
    WEEKLY_INTERVAL_DAYS,
    format_countdown,
    load_bonus_info,
    save_bonus_info,
)


class DailyWorkflow(Workflow):
    """Run the daily Mines/Dice + chest-claim routine across all accounts."""

    name = "Daily Tasks"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_daily)

    def _result_path(self) -> Path:
        return settings.result_dir / "daily_data" / "result.xlsx"

    def save_results(self, results: list[AccountResult]) -> None:
        if not results:
            return
        save_statistics(results, self._result_path())
        dated = self._result_path().with_name(f"result_{datetime.now():%d.%m}.xlsx")
        save_statistics(results, dated)

    def _log_bonus_countdown(self, worker_id: str, ud_dir: str) -> None:
        try:
            info = load_bonus_info(str(ud_dir))
            log.step(worker_id, "📅", "Weekly bonus", format_countdown(info["weekly_claimed_at"], WEEKLY_INTERVAL_DAYS))
            log.step(worker_id, "📅", "Monthly bonus", format_countdown(info["monthly_claimed_at"], MONTHLY_INTERVAL_DAYS))
        except Exception as exc:  # noqa: BLE001
            log.warning(f"[{worker_id}] Could not read bonus tracker: {exc}")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Worker-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link
        trigger = get_trigger()

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
                    page, account.link, worker_id
                )
                if not auth_success or start_balance is None:
                    log.step(worker_id, "❌", "Could not read balance after auth")
                    result.RESULT = ResultStatus.AUTH_FAILED.value
                    return result
                result.START_BALANCE = start_balance

                start_sol_balance = await get_sol_balance(page, worker_id)
                if start_sol_balance is not None:
                    result.START_SOL_BALANCE = start_sol_balance

                if trigger == "after_login":
                    await try_withdraw_in_daily(page, account, worker_id, start_balance, result)

                await self._gather_links(page, account, worker_id, result)

                log.step(worker_id, "📅", "Bonus countdown:")
                self._log_bonus_countdown(worker_id, account.get("UD_DIR", account.user_data_dir))

                await self._read_chest_amount(page, worker_id, result)

                log.step(worker_id, "⏰", "Checking Renew Play Timer...")
                context = browser.contexts[0] if browser and browser.contexts else None
                if await check_and_renew_playtimer(page, account, worker_id, context) is False:
                    log.step(worker_id, "❌", "Critical renew error. Aborting.")
                    result.RESULT = ResultStatus.RENEW_CRITICAL_ERROR.value
                    return result

                if not await self._handle_chest(page, worker_id, account, result, start_balance):
                    return result

                log.step(worker_id, "🎮", "Starting game...")
                await execute_game_logic(page, result, index)

                end_balance, end_sol, sol_diff = await process_final_balance(
                    page, account.link, worker_id, result.to_dict()
                )
                result.END_BALANCE = end_balance
                result.BALANCE_DIFFERENCE = calculate_balance_difference(start_balance, end_balance)
                if end_sol is not None:
                    result.END_SOL_BALANCE = end_sol
                if sol_diff is not None:
                    result.SOL_BALANCE_DIFFERENCE = sol_diff

                if trigger == "after_game":
                    await try_withdraw_in_daily(page, account, worker_id, end_balance, result)

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

    async def _gather_links(self, page, account: Account, worker_id: str, result: AccountResult) -> None:
        """Fetch login link / external wallet / saved-session connect, in random order."""
        steps = [
            (get_link_for_login, "LOGIN_LINK", "Login link fetched"),
            (get_external_wallet, "EXTERNAL_WALLET", "Internal wallet"),
            (wallet_connect_session, "WALLET_CONNECTED", "Wallet connected (saved session)"),
        ]
        random.shuffle(steps)
        try:
            await page.click('button:has-text("Do Nothing")', timeout=3000)
        except Exception:  # noqa: BLE001
            pass
        for func, key, success_msg in steps:
            value = await func(page)
            if value == "SKIPPED":
                result.extra[key] = "SKIPPED"
                log.step(worker_id, "⏩", "Wallet button not found, skipping...")
                continue
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

    async def _read_chest_amount(self, page, worker_id: str, result: AccountResult) -> None:
        try:
            value = await page.locator("button div.css-18rpzfs").inner_text(timeout=5000)
            result.CHEST_AMOUNT = float(value.replace("$", "").replace(",", ""))
            log.step(worker_id, "💰", f"Chest amount: ${result.CHEST_AMOUNT}")
        except Exception:  # noqa: BLE001
            result.CHEST_AMOUNT = 0.0
            log.warning(f"[{worker_id}] Chest amount not found")

    async def _handle_chest(
        self, page, worker_id: str, account: Account, result: AccountResult, start_balance
    ) -> bool:
        """Returns False if the workflow should stop early for this account."""
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
                claim = await process_chest(page, worker_id)
                try:
                    save_bonus_info(
                        ud_dir=str(account.get("UD_DIR", account.user_data_dir)),
                        weekly_claimed=claim.get("weekly_claimed", False),
                        monthly_claimed=claim.get("monthly_claimed", False),
                    )
                except Exception as bt_err:  # noqa: BLE001
                    log.warning(f"[{worker_id}] Bonus tracker save error: {bt_err}")
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


async def run_daily(workers: int | None = None) -> None:
    """Entry point used by the CLI."""
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    workflow = DailyWorkflow(workers or settings.concurrency.max_workers)
    await workflow.run()
