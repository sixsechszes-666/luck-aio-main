"""Luck.io balance, chest-status and login-link reads.

The Luck.io-domain half of the legacy ``luck_browser.py`` (the browser-mechanics
half — QR decoding, captcha — lives under :mod:`luckflow.browser`). These are
pure reads against the rendered page; orchestration that also *acts* (connect
wallet, prepare account) lives in :mod:`luckflow.platform.connect`.
"""

from __future__ import annotations

import asyncio
import random
import re

from luckflow.browser.session import get_and_decode_qr_code
from luckflow.core import logging as log


async def get_balance_value(page, timeout: int = 30000) -> str:
    """Read the USD balance, returned as a comma-decimal string (e.g. ``"12,34"``)."""
    try:
        await page.wait_for_selector(".css-1sg2lsz", timeout=timeout)
        price_element = page.locator('.css-1mmloj8 div:has-text("≈$")')
        await price_element.wait_for(state="visible", timeout=timeout)
        value = await price_element.text_content()

        if value and value.strip():
            cleaned = value.replace("≈", "").replace("$", "").strip()
            try:
                number = float(cleaned)
                formatted = f"{number:.2f}".replace(".", ",")
                log.info("💰 Balance", formatted)
                return formatted
            except ValueError:
                log.warning("Could not parse balance value", cleaned)
                return "0,00"
        log.warning("Balance value is empty")
        return "0,00"
    except Exception as exc:  # noqa: BLE001
        log.error("Error reading balance", str(exc))
        return "0,00"


async def get_sol_balance(page, worker_id: str) -> float | None:
    """Read the SOL balance from the page header."""
    try:
        sol_element = page.locator(".css-1mmloj8 div:nth-child(2)")
        await sol_element.wait_for(state="visible", timeout=3000)
        sol_text = await sol_element.text_content()
        if sol_text:
            match = re.search(r"([\d.]+)", sol_text)
            if match:
                sol_balance = float(match.group(1))
                log.step(worker_id, "🪙", "SOL balance", f"{sol_balance} SOL")
                return sol_balance
            log.step(worker_id, "⚠️ ", f"Could not extract SOL value from: {sol_text}")
        else:
            log.step(worker_id, "⚠️ ", "SOL element empty")
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id, "⚠️ ", "Error reading SOL balance", str(exc))
    return None


async def process_final_balance(
    page, link: str, worker_id: str, account_stats: dict
) -> tuple[str, float | None, float | None]:
    """Navigate back to ``link``, read final USD+SOL balance, compute SOL delta."""
    log.step(worker_id, "💰", "Checking final balance...")
    await page.goto(link)
    await asyncio.sleep(3)

    end_balance = await get_balance_value(page, timeout=30000)
    end_sol_balance = await get_sol_balance(page, worker_id)

    sol_difference = None
    start_sol = account_stats.get("START_SOL_BALANCE")
    if end_sol_balance is not None and start_sol is not None:
        sol_difference = end_sol_balance - start_sol
        log.step(worker_id, "🪙", "SOL change", f"{sol_difference:+.6f} SOL")
    elif end_sol_balance is not None:
        log.step(worker_id, "🪙", "SOL balance read (no start balance recorded)")

    return end_balance, end_sol_balance, sol_difference


async def get_chest_status(page) -> str:
    """Return the daily chest state: ``available`` / ``unavailable`` / ``not_found``."""
    try:
        log.info("📦 Checking chest status...")
        for button in await page.locator('button:has(img[src*="chest-"])').all():
            src = await button.locator("img").get_attribute("src")
            if src and "chest-available" in src:
                log.success("✅ Chest available")
                return "available"
            if src and "chest-unavailable" in src:
                log.warning("⏰ Chest on cooldown")
                return "unavailable"
        log.warning("❓ Chest not found on page")
        return "not_found"
    except Exception as exc:  # noqa: BLE001
        log.error("Error checking chest", str(exc))
        return "not_found"


async def get_link_for_login(page, link_refresh: bool = False) -> str | None:
    """Open the Mobile Login flow and decode the QR into a login URL."""
    for attempt in range(5):
        try:
            if link_refresh:
                await page.goto("https://luck.io/")
            await asyncio.sleep(3)

            await page.locator("button.css-1wc7o8w").nth(1).click()
            await page.locator("div.css-1ber6xn:has-text('Mobile Login')").click()
            await page.get_by_text("Anyone with this link or QR").click()
            await page.get_by_text("I am not streaming or sharing").click()

            decoded_url = await get_and_decode_qr_code(page)
            if decoded_url:
                log.info("🔗 Login link", decoded_url[:60])
                await page.locator(".css-ylk4v3").click()
                return decoded_url
            log.warning("Could not decode QR code")
            break
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Error getting login link (attempt {attempt + 1})", str(exc))
            continue
    log.error("Could not get login link")
    return None


async def get_external_wallet(page, link_refresh: bool = False) -> str | None:
    """Read the internal/external wallet address from the account page."""
    for attempt in range(5):
        try:
            if link_refresh:
                await page.goto("https://luck.io/")
            await asyncio.sleep(random.uniform(2, 4))
            await page.locator("button.css-13t37m3").click()
            await asyncio.sleep(random.uniform(1, 3))
            href = await page.locator("td.css-39ve67 a").get_attribute("href")
            address = href.split("/account/")[-1] if "/account/" in href else href.split("/")[-1]
            if address:
                log.info("🏦 Internal wallet", address[:20] + "...")
                return address
            log.warning("Could not read internal wallet address")
            break
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Error reading internal wallet (attempt {attempt + 1})", str(exc))
            continue
    log.error("Could not read internal wallet address")
    return None


async def get_available_amount(page, timeout: int = 20000) -> float | None:
    """Read the available (withdrawable) amount."""
    try:
        amount_element = page.locator(".css-1d14ggf")
        await amount_element.wait_for(state="visible", timeout=timeout)
        text = await amount_element.text_content()
        numbers = re.findall(r"([\d.]+)", text)
        if numbers:
            amount = float(numbers[0])
            log.info("💰 Available amount", str(amount))
            return amount
        log.warning("No number found in amount text", text)
        return None
    except Exception as exc:  # noqa: BLE001
        log.error("Error reading available amount", str(exc))
        return None
