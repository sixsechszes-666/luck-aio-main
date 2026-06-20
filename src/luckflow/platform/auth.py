"""Wallet-based authentication and start-balance retrieval.

Ported from ``projects/auth.py``. The legacy version received ``connect_wallet``,
``get_balance_value`` and ``get_timestamp`` as **function arguments** to dodge a
circular import. That hack is removed: collaborators are imported directly.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from luckflow.core import logging as log
from luckflow.platform.balance import get_balance_value
from luckflow.platform.connect import connect_wallet

ConnectFn = Callable[[object], Awaitable[None]]


async def authenticate_and_get_balance(
    page, link: str, worker_id: str, connect: ConnectFn | None = None
) -> tuple[str | None, bool]:
    """Authenticate via the wallet and read the starting balance.

    ``connect`` selects the wallet-connection strategy (defaults to
    :func:`~luckflow.platform.connect.connect_wallet`; registration/warmup flows
    pass ``connect_wallet_registration``). Returns ``(balance, success)``.
    """
    connect = connect or connect_wallet
    for attempt in range(3):
        try:
            await page.goto(link)
            log.step(worker_id, "✓ ", f"Page loaded (attempt {attempt + 1})")
            await page.wait_for_selector(".css-1sg2lsz", timeout=30000)

            balance = await _attempt_balance_retrieval(page, worker_id, connect)
            if balance is not None:
                return balance, True
        except Exception as exc:  # noqa: BLE001
            log.step(worker_id, "⚠️ ", f"Attempt {attempt + 1}", str(exc)[:50])
            if attempt == 2:
                raise
            continue
    return None, False


async def _attempt_balance_retrieval(page, worker_id: str, connect: ConnectFn) -> str | None:
    """Try to read the balance, connecting the wallet on failure."""
    for _ in range(5):
        try:
            price_element = page.locator('.css-1mmloj8 div:has-text("≈$")')
            await price_element.wait_for(state="visible", timeout=3000)
            start_balance = await get_balance_value(page, timeout=15000)
            log.step(worker_id, "💰", f"Balance: ${start_balance}")
            return start_balance
        except Exception:  # noqa: BLE001
            try:
                await page.click('button:has-text("Do Nothing")', timeout=1000)
            except Exception:  # noqa: BLE001
                pass
            log.step(worker_id, "🔄", "Connecting wallet...")
            await connect(page)
            if not await _handle_wallet_connection_with_retry(page, worker_id):
                continue
    return None


async def _handle_wallet_connection_with_retry(page, worker_id: str) -> bool | None:
    """Confirm the wallet connection, retrying on "too many requests"."""
    try_count = 0
    context = page.context
    while True:
        try:
            if try_count > 0:
                try_count += 1
                waiting_time = random.uniform(35, 50)
                log.info(f"⏳ Waiting {waiting_time:.1f}s...")
                await asyncio.sleep(waiting_time)
                await page.locator("button:has-text('Login')").nth(1).click()
                connection_page = await _get_connection_page(page, context)
                await connection_page.click("button.btn-primary", timeout=20_000)
                if await _check_rate_limit_error(page, worker_id, waiting_time, try_count):
                    continue
                return True
            else:
                try_count += 1
                if await _check_rate_limit_error(page, worker_id, None, try_count):
                    continue
                return True
        except Exception as loop_error:  # noqa: BLE001
            log.step(worker_id, "⚠️ ", "Error in connection loop", str(loop_error)[:50])
            return False


async def _get_connection_page(page, context):
    """Obtain the wallet-confirmation popup page, selecting Solflare if needed."""
    try:
        log.info("⏳ Waiting for confirmation window...")
        connection_page = await context.wait_for_event("page", timeout=5_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        return connection_page
    except Exception:  # noqa: BLE001
        log.info("🦊 Selecting Solflare...")
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=500)
        except Exception:  # noqa: BLE001
            log.warning("Solflare button not found")
        log.info("⏳ Waiting for confirmation window...")
        connection_page = await context.wait_for_event("page", timeout=5_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        log.success("✅ Confirming connection...")
        await connection_page.bring_to_front()
        return connection_page


async def _check_rate_limit_error(
    page, worker_id: str, waiting_time: float | None, try_count: int
) -> bool:
    """True if a "too many requests" error is visible (caller should retry)."""
    try:
        error_element = page.locator(".css-w1u0kl")
        await error_element.wait_for(state="visible", timeout=5000)
        error_text = (await error_element.inner_text()).lower()
        if "too many requests" in error_text or "please try again later" in error_text:
            suffix = f"waiting {waiting_time:.1f}s | attempt {try_count}" if waiting_time else f"attempt {try_count}"
            log.error(f"[{worker_id}] Rate limited (IP throttling)", suffix)
            return True
        return False
    except Exception:  # noqa: BLE001
        return False
