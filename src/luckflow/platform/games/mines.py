"""Mines game: setup (field size, safe cells, bet) and auto-cashout play loop."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.utils import balance_decreased
from luckflow.platform.games.base import click_random_in_area, place_random_bet


async def mines_setup(
    page,
    mines_count: str | int | None = None,
    safe_cells: str | int | None = None,
    timeout: int = 30000,
) -> bool:
    """Open Mines, place a bet, choose field size and safe-cell count."""
    mines_count = str(mines_count if mines_count is not None else settings.game.mines_count)
    safe_cells = str(safe_cells if safe_cells is not None else settings.game.mines_safe_cells)
    try:
        log.info("🎮 Opening Mines page...")
        await page.goto("https://luck.io/mines")
        try:
            await page.wait_for_selector("div.css-mi8v6c", timeout=timeout)
            log.success("✅ Mines page loaded")
        except Exception as exc:  # noqa: BLE001
            log.error("Error loading Mines", str(exc))
            return False

        log.info("⚙️  Configuring parameters...")
        await place_random_bet(page, timeout)

        log.info(f"📐 Choosing field size: {mines_count} cells")
        await page.wait_for_selector('[id^="luckio-field-"]', timeout=timeout)
        btn_field_size = page.locator(f'[id^="luckio-field-"] >> button:has-text("{mines_count}")').first
        await btn_field_size.wait_for(state="visible", timeout=timeout)
        await btn_field_size.click()
        log.success(f"✓ Field size set: {mines_count}")
        await page.wait_for_timeout(2000)

        log.info(f"⚡ Setting safe cells: {safe_cells}")
        slider = page.locator('[id^="luckio-field-"] input[type="range"]')
        await slider.wait_for(state="visible", timeout=timeout)
        await slider.fill(str(safe_cells))

        mines_on_field = int(mines_count) - int(safe_cells)
        log.separator()
        log.info("📊 Mines config")
        log.detail("Field size", f"{mines_count} cells")
        log.detail("Safe cells", str(safe_cells))
        log.detail("Mines on field", str(mines_on_field))

        current_value = await slider.get_attribute("value")
        if current_value != str(safe_cells):
            log.warning(f"Slider: {current_value}, expected: {safe_cells}")
        log.success("✅ Mines setup complete")
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Error setting up Mines", str(exc))
        try:
            log.info("🌐 Current URL", page.url)
        except Exception:  # noqa: BLE001
            pass
        return False


async def mines_play(
    page,
    min_rounds: int | None = None,
    max_rounds: int | None = None,
    min_clicks: int | None = None,
    max_clicks: int | None = None,
    balance_timeout: int = 60000,
    cashout_timeout: int = 3000,
    enable_balance_check: bool | None = None,
) -> dict[str, Any]:
    """Play Mines for a random number of rounds, cashing out each round."""
    from luckflow.platform.balance import get_balance_value

    game = settings.game
    min_rounds = min_rounds if min_rounds is not None else game.mines_min_rounds
    max_rounds = max_rounds if max_rounds is not None else game.mines_max_rounds
    min_clicks = min_clicks if min_clicks is not None else game.mines_min_clicks
    max_clicks = max_clicks if max_clicks is not None else game.mines_max_clicks
    if enable_balance_check is None:
        enable_balance_check = game.enable_balance_check

    log.info("🎮 Starting Mines...")
    if enable_balance_check:
        previous_balance = await get_balance_value(page, timeout=balance_timeout) or "$0,00"
        log.info(f"💰 Start balance: {previous_balance}")
    else:
        previous_balance = "0,00"
    initial_balance = previous_balance

    if enable_balance_check:
        def _to_float(value: str) -> float | None:
            try:
                return float(value.replace(",", ".")) if "," in value else float(value)
            except (ValueError, AttributeError):
                return None

        start_value = _to_float(previous_balance)
        if start_value is not None and start_value < game.min_balance:
            log.warning(f"Balance {start_value:.4f}$ too small — round skipped")
            return {
                "rounds_played": 0,
                "successful_cashouts": 0,
                "planned_rounds": 0,
                "start_balance": previous_balance,
                "final_balance": previous_balance,
                "success_rate": 0,
            }

    rounds_played = 0
    successful_cashouts = 0
    total_rounds = random.randint(min_rounds, max_rounds)
    log.info(f"🎯 Planning {total_rounds} rounds")
    log.separator()

    try:
        for round_num in range(1, total_rounds + 1):
            log.info(f"🔄 Round {round_num}/{total_rounds}")
            if enable_balance_check:
                current_balance = await get_balance_value(page, timeout=balance_timeout)
                if current_balance is None:
                    log.error("Could not read balance, stopping")
                    break
                if current_balance != previous_balance:
                    log.info(f"📊 Balance changed: {previous_balance} → {current_balance}")
                if balance_decreased(previous_balance, current_balance):
                    log.info("🛑 Balance dropped, stopping")
                    break
                previous_balance = current_balance
            try:
                log.info("▶️  Clicking Play")
                await page.locator("button.bet-button").click()
                await asyncio.sleep(random.uniform(3, 5))

                clicks_count = random.randint(min_clicks, max_clicks)
                log.info(f"🎯 Making {clicks_count} field clicks")
                for _ in range(clicks_count):
                    await click_random_in_area(page)

                log.info("💸 Waiting for Cash Out...")
                for _ in range(10):
                    try:
                        await page.wait_for_selector('button:has-text("Cash Out")', timeout=cashout_timeout)
                        cash_out = page.locator('button:has-text("Cash Out")')
                        await cash_out.wait_for(state="visible")
                        await cash_out.click(timeout=1000)
                        break
                    except Exception:  # noqa: BLE001
                        await click_random_in_area(page)
                        continue

                log.success("✅ Cash Out done")
                successful_cashouts += 1
                rounds_played += 1
                await asyncio.sleep(random.uniform(3, 5))
            except Exception as exc:  # noqa: BLE001
                log.error(f"Error in round {round_num}", str(exc))
                rounds_played += 1
                continue
    except Exception as exc:  # noqa: BLE001
        log.error("Critical game error", str(exc))

    final_balance = "unknown"
    if enable_balance_check:
        final_balance = await get_balance_value(page, timeout=balance_timeout) or "unavailable"

    result = {
        "rounds_played": rounds_played,
        "successful_cashouts": successful_cashouts,
        "planned_rounds": total_rounds,
        "start_balance": initial_balance if enable_balance_check else "untracked",
        "final_balance": final_balance,
        "success_rate": (successful_cashouts / rounds_played * 100) if rounds_played else 0,
    }
    log.info("📊 Mines stats", f"{rounds_played}/{total_rounds}, cashouts {successful_cashouts}")
    return result
