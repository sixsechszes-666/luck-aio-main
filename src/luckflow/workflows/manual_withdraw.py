"""Manual-withdraw workflow: open browsers and fetch login links for manual work.

Ported from ``withdraw_manual`` / ``withdraw_handler`` in ``luck_main.py``.
Browsers are left **open** for the operator unless an error or rate-limit occurs.
"""

from __future__ import annotations

from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    launch_ixbrowser_profile,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult, ResultStatus
from luckflow.core.workflow import Workflow
from luckflow.platform.balance import get_balance_value, get_link_for_login, get_sol_balance
from luckflow.platform.connect import connect_wallet
from luckflow.storage import load_accounts, save_statistics


class ManualWithdrawWorkflow(Workflow):
    """Prepare each account for manual withdrawal and leave its browser open."""

    name = "Manual Withdraw"

    def load_accounts(self) -> list[Account]:
        return load_accounts(settings.excel_daily)

    def save_results(self, results: list[AccountResult]) -> None:
        if results:
            save_statistics(results, settings.result_dir / "result_manual_withdraw.xlsx")

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

            for attempt in range(3):
                try:
                    await page.goto(account.link)
                    await page.wait_for_selector(".css-1sg2lsz", timeout=30000)
                    for _ in range(5):
                        try:
                            price_element = page.locator('.css-1mmloj8 div:has-text("≈$")')
                            await price_element.wait_for(state="visible", timeout=3000)
                            result.START_BALANCE = await get_balance_value(page, timeout=15000)
                            result.START_SOL_BALANCE = await get_sol_balance(page, worker_id)
                            break
                        except Exception:  # noqa: BLE001
                            try:
                                await page.click('button:has-text("Do Nothing")', timeout=1000)
                            except Exception:  # noqa: BLE001
                                pass
                            log.step(worker_id, "🔄", "Connecting wallet...")
                            await connect_wallet(page)
                            try:
                                error_element = page.locator('.css-w1u0kl:has-text("too many requests")')
                                await error_element.wait_for(state="visible", timeout=3000)
                                if "too many requests" in (await error_element.inner_text()).lower():
                                    log.step(worker_id, "❌", "Rate limited — skipping account")
                                    result.RESULT = ResultStatus.TOO_MANY_REQUESTS.value
                                    result.END_BALANCE = result.START_BALANCE or 0
                                    result.BALANCE_DIFFERENCE = 0
                                    should_close = True
                                    return result
                            except Exception:  # noqa: BLE001
                                pass
                            continue
                    try:
                        await page.click('button:has-text("Do Nothing")', timeout=1000)
                    except Exception:  # noqa: BLE001
                        pass
                    break
                except Exception as exc:  # noqa: BLE001
                    log.step(worker_id, "⚠️ ", f"Attempt {attempt + 1}", str(exc)[:50])
                    if attempt == 2:
                        raise
                    continue

            log.step(worker_id, "🔗", "Getting login link...")
            try:
                login_link = await get_link_for_login(page, link_refresh=True)
                if login_link:
                    result.LOGIN_LINK = login_link
                    result.RESULT = ResultStatus.SUCCESS.value
                else:
                    result.RESULT = "NO_LOGIN_LINK"
            except Exception as exc:  # noqa: BLE001
                result.RESULT = f"LINK_ERROR: {str(exc)[:50]}"
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


async def run_manual_withdraw(workers: int | None = None) -> None:
    from luckflow.core.runner import install_asyncio_exception_handler

    install_asyncio_exception_handler()
    await ManualWithdrawWorkflow(workers or settings.concurrency.max_withdraw).run()
