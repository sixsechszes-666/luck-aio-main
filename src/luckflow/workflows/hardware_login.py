"""Hardware-login workflow: log in, claim chest, play, then leave the browser open.

Ported from ``hardware_login`` / ``hardware_login_handler`` in ``luck_main.py``.
Browsers stay open for manual hardware-wallet work unless an error occurs.
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
from luckflow.core.utils import calculate_balance_difference
from luckflow.core.workflow import Workflow
from luckflow.platform.auth import authenticate_and_get_balance
from luckflow.platform.balance import (
    get_balance_value,
    get_chest_status,
    get_link_for_login,
    get_sol_balance,
)
from luckflow.platform.chest import process_chest
from luckflow.platform.games import execute_game_logic
from luckflow.storage import load_accounts, save_statistics


class HardwareLoginWorkflow(Workflow):
    """Authenticate, claim chest, play a game, then leave the browser open."""

    name = "Hardware Login"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_hardware)

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "result_hardware.xlsx")

    async def process_account(self, account: Account, index: int, total: int) -> AccountResult:
        worker_id = f"Worker-{index + 1:03d}"
        result = AccountResult.new(worker_id)
        result.UD_DIR = account.user_data_dir
        result.LINK = account.link

        playwright = browser = page = client = None
        should_close = False
        log.progress(index + 1, total, f"ID:{account.user_data_dir}")
        try:
            log.step(worker_id, "🎯", "Launching browser...")
            playwright, browser, page, client = await launch_ixbrowser_profile(account.profile_id)
            try:
                await clear_pages(browser.contexts[0] if browser.contexts else None, page)
            except Exception:  # noqa: BLE001
                pass

            start_balance, auth_success = await authenticate_and_get_balance(page, account.link, worker_id)
            if not auth_success or start_balance is None:
                log.error(f"[{worker_id}] Could not read balance after auth")
                result.RESULT = ResultStatus.AUTH_FAILED.value
                return result
            result.START_BALANCE = start_balance

            log.step(worker_id, "🔗", "Getting login link...")
            try:
                login_link = await get_link_for_login(page, link_refresh=True)
                if login_link:
                    result.LOGIN_LINK = login_link
                else:
                    result.RESULT = "NO_LOGIN_LINK"
            except Exception as exc:  # noqa: BLE001
                result.RESULT = f"LINK_ERROR: {str(exc)[:50]}"

            try:
                await asyncio.sleep(1)
                log.step(worker_id, "📦", "Checking chest...")
                chest_status = await get_chest_status(page)
                if chest_status == "unavailable":
                    log.error(f"[{worker_id}] Chest unavailable")
                    self._freeze(result, start_balance)
                    result.RESULT = ResultStatus.CHEST_UNAVAILABLE.value
                    return result
                if chest_status == "available":
                    try:
                        await process_chest(page, worker_id)
                    except Exception as chest_error:  # noqa: BLE001
                        log.step(worker_id, "🚫", "Chest error", str(chest_error))
                        self._freeze(result, start_balance)
                        result.RESULT = ResultStatus.CHEST_CRITICAL_ERROR.value
                        return result
                elif chest_status == "not_found":
                    log.step(worker_id, "⚠️ ", "Chest not found")

                log.step(worker_id, "🎮", "Starting game...")
                await execute_game_logic(page, result, index)

                await page.goto(account.link)
                await asyncio.sleep(3)
                end_balance = await get_balance_value(page, timeout=30000)
                result.END_BALANCE = end_balance
                result.BALANCE_DIFFERENCE = calculate_balance_difference(start_balance, end_balance)
                end_sol = await get_sol_balance(page, worker_id)
                if end_sol is not None:
                    result.END_SOL_BALANCE = end_sol
                    if result.START_SOL_BALANCE is not None:
                        result.SOL_BALANCE_DIFFERENCE = end_sol - result.START_SOL_BALANCE
                log.step(worker_id, "✅", f"Done | ${end_balance} | {result.BALANCE_DIFFERENCE}")
                result.RESULT = ResultStatus.SUCCESS.value
            except Exception as exc:  # noqa: BLE001
                log.error(f"[{worker_id}] Game error", str(exc)[:50])
                result.RESULT = f"GAME_ERROR: {str(exc)[:50]}"
            log.step(worker_id, "🏁", "Done. Browser left open.")
        except Exception as exc:  # noqa: BLE001
            log.error(f"[{worker_id}] Runtime error", str(exc)[:50])
            result.RESULT = f"RUNTIME_ERROR: {str(exc)[:50]}"
            should_close = True
        finally:
            if should_close:
                await cleanup_browser_resources(page, browser, playwright, client, account.profile_id, f"[{worker_id}]")
            else:
                log.step(worker_id, "🔓", "Browser left open for manual work")
        return result

    @staticmethod
    def _freeze(result: AccountResult, start_balance) -> None:
        result.END_BALANCE = start_balance
        result.END_SOL_BALANCE = result.START_SOL_BALANCE
        if result.START_SOL_BALANCE is not None:
            result.SOL_BALANCE_DIFFERENCE = 0.0


async def run_hardware_login(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await HardwareLoginWorkflow(workers or settings.concurrency.max_workers).run()
