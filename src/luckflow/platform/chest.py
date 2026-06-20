"""Daily-chest claiming, including weekly/monthly bonus handling.

Ported from ``process_chest`` / ``process_chest_volume`` in ``luck_wallet.py``.
``process_chest`` claims the daily reload then weekly+monthly bonuses;
``process_chest_volume`` (used by the warmup-volume workflow) skips the daily
reload and goes straight to the weekly/monthly bonuses. Selectors and the
``ChestProcessingError`` semantics are preserved.
"""

from __future__ import annotations

import asyncio
import re

from luckflow.core import logging as log
from luckflow.core.exceptions import ChestProcessingError


async def _claim_weekly_bonus(page, worker_id: str, claim_result: dict) -> None:
    log.step(worker_id, "🔍", "Checking weekly bonus...")
    weekly_container = page.locator('div.css-1822ru2:has(img[src*="weekly-bonus"])')
    btn = weekly_container.locator('button.css-7r8uz7:has-text("Claim")')
    try:
        if await btn.is_visible():
            if await btn.get_attribute("disabled") is None:
                log.step(worker_id, "🎁", "Weekly bonus available!")
                await btn.click()
                await page.click('button.css-1oqonge:has-text("Play")', timeout=60_000)
                claim_button = page.locator('div:has-text("Daily Reload") button:has-text("Claim")').first
                await claim_button.click(timeout=10000)
                await asyncio.sleep(3)
                log.step(worker_id, "✅", "Weekly bonus claimed")
                claim_result["weekly_claimed"] = True
                await page.wait_for_selector('button:has-text("Continue Playing")', timeout=10000)
                await page.get_by_text("Continue Playing").click()
            else:
                log.step(worker_id, "⏳", "Weekly bonus not yet available (disabled)")
        else:
            log.step(worker_id, "❌", "Weekly bonus button not found")
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id, "❌", "Error checking weekly bonus", str(exc))


async def _claim_monthly_bonus(page, worker_id: str, claim_result: dict) -> None:
    log.step(worker_id, "🔍", "Checking monthly bonus...")
    btn = page.locator("div").filter(has_text=re.compile(r"^Monthly BonusClaim$")).get_by_role("button")
    try:
        if await btn.is_visible():
            if await btn.get_attribute("disabled") is None:
                log.step(worker_id, "🎁", "Monthly bonus available!")
                await btn.click()
                await page.click('button.css-1oqonge:has-text("Play")', timeout=60_000)
                claim_button = page.locator('div:has-text("Daily Reload") button:has-text("Claim")').first
                await claim_button.click(timeout=10000)
                await asyncio.sleep(3)
                log.step(worker_id, "✅", "Monthly bonus claimed")
                claim_result["monthly_claimed"] = True
            else:
                log.step(worker_id, "⏳", "Monthly bonus not yet available (disabled)")
        else:
            log.step(worker_id, "❌", "Monthly bonus button not found")
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id, "❌", "Error claiming monthly bonus", str(exc))


async def _open_available_chest(page, worker_id: str) -> None:
    log.step(worker_id, "🎯", "Looking for available chest...")
    available_chest = page.locator('button:has(img[src*="chest-available"])')
    await available_chest.wait_for(state="visible", timeout=10000)
    await available_chest.click()
    log.step(worker_id, "✅", "Chest found and opened")
    try:
        log.step(worker_id, "⚡", "Attempting activation...")
        await page.get_by_role("button", name="Activate").click(timeout=2000)
        log.step(worker_id, "✅", "Activated")
    except Exception:  # noqa: BLE001
        log.step(worker_id, "⚠️ ", "Activate button not found")


async def process_chest(page, worker_id: str) -> dict:
    """Claim the daily reload, then weekly and monthly bonuses.

    Returns ``{'weekly_claimed': bool, 'monthly_claimed': bool}``.
    """
    claim_result = {"weekly_claimed": False, "monthly_claimed": False}
    log.step(worker_id, "📦", "Processing chest...")
    try:
        await _open_available_chest(page, worker_id)
        try:
            log.step(worker_id, "🔍", "Looking for Claim button...")
            await page.wait_for_selector('button:has-text("Claim")', timeout=2000)
            claim_button = page.locator('div:has-text("Daily Reload") button:has-text("Claim")').first
            if await claim_button.get_attribute("disabled") is not None:
                log.step(worker_id, "⚠️ ", "Daily claim unavailable")
                raise ChestProcessingError("Daily claim unavailable")

            log.step(worker_id, "🎁", "Claiming daily bonus...")
            await claim_button.click(timeout=2000)
            log.step(worker_id, "✅", "Daily bonus claimed")

            log.step(worker_id, "▶️ ", "Continuing play...")
            await page.wait_for_selector('button:has-text("Continue Playing")', timeout=10000)
            await page.get_by_text("Continue Playing").click()
            log.step(worker_id, "✅", "Play continued")

            await _claim_weekly_bonus(page, worker_id, claim_result)
            await _claim_monthly_bonus(page, worker_id, claim_result)
        except ChestProcessingError:
            raise
        except Exception as claim_error:  # noqa: BLE001
            log.step(worker_id, "❌", "Critical chest error", str(claim_error))
            raise ChestProcessingError(f"Critical chest error: {claim_error}") from claim_error
    except ChestProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id, "❌", "General chest error", str(exc))
        raise ChestProcessingError(f"General chest error: {exc}") from exc
    return claim_result


async def process_chest_volume(page, worker_id: str) -> dict:
    """Like :func:`process_chest` but skips the daily reload (warmup-volume mode)."""
    claim_result = {"weekly_claimed": False, "monthly_claimed": False}
    log.step(worker_id, "📦", "Processing chest...")
    try:
        await _open_available_chest(page, worker_id)
        try:
            await _claim_weekly_bonus(page, worker_id, claim_result)
            await _claim_monthly_bonus(page, worker_id, claim_result)
        except ChestProcessingError:
            raise
        except Exception as claim_error:  # noqa: BLE001
            log.step(worker_id, "❌", "Critical chest error", str(claim_error))
            raise ChestProcessingError(f"Critical chest error: {claim_error}") from claim_error
    except ChestProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id, "❌", "General chest error", str(exc))
        raise ChestProcessingError(f"General chest error: {exc}") from exc
    return claim_result
