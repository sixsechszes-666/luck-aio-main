"""Shared game primitives.

The legacy ``luck_games.py`` repeated the same bet-placement block in all four
game setups, and the dice/limbo/hellspin play loops were near-identical. Those
are unified here:

* :func:`place_random_bet` — read USD balance, compute a small-biased random bet.
* :func:`setup_multiplier_game` — generic setup for dice/limbo/hellspin.
* :func:`play_multiplier_game` — generic play loop for dice/limbo/hellspin.
* :func:`click_random_in_area` — Mines field clicking.

Behaviour (selectors, beta-distribution bet, balance-drop stop) is preserved.
"""

from __future__ import annotations

import asyncio
import random
import re
from typing import Any

from luckflow.core import logging as log

# Inter-round delay ranges differ between games in the original code.
DICE_INTER_ROUND_DELAY = (0.5, 1.0)
LIMBO_INTER_ROUND_DELAY = (0.5, 3.0)
HELL_INTER_ROUND_DELAY = (0.5, 3.0)


async def place_random_bet(page, timeout: int = 30000) -> float | None:
    """Read the USD balance and type a small-biased random bet.

    Returns the balance read, or ``None`` if it could not be parsed.
    """
    usd_locator = page.locator('div.css-1mmloj8 >> div[style*="color: rgb(141, 138, 168)"]')
    await usd_locator.wait_for(state="visible", timeout=60000)
    usd_text = await usd_locator.text_content()
    usd_balance = float(re.search(r"\$([\d.]+)", usd_text).group(1))

    max_bet = min(usd_balance * 0.9, 0.6)
    if usd_balance < 0.10:
        log.error(f"Insufficient funds! Balance: ${usd_balance}, minimum: $0.10")
        return usd_balance

    # Beta(2, 10) biases the bet toward smaller values.
    random_factor = random.betavariate(2, 10)
    final_bet = round(0.10 + (max_bet - 0.10) * random_factor, 2)

    field = page.locator('div.css-1ikdrop >> input[type="text"][autocomplete="off"]').first
    await field.wait_for(state="visible", timeout=60000)
    await field.click(click_count=3)
    await page.keyboard.type(str(final_bet), delay=100)

    log.info(f"💰 Balance: ${usd_balance}")
    log.info(f"🎯 Bet: ${final_bet} (random, small-biased)")
    return usd_balance


async def click_random_in_area(page, x1=383, y1=103, x2=724, y2=448) -> tuple[int, int]:
    """Double-click a random point inside the given rectangle (Mines field)."""
    x = random.randint(x1, x2)
    y = random.randint(y1, y2)
    for _ in range(2):
        await page.mouse.click(x, y)
        await asyncio.sleep(random.uniform(0.2, 0.5))
    await asyncio.sleep(random.uniform(1, 2))
    log.info(f"🎯 Clicked at ({x}, {y})")
    return x, y


async def setup_multiplier_game(
    page, url: str, name: str, multiplier: float, timeout: int = 30000
) -> bool:
    """Generic setup for multiplier games (Dice, Limbo, Hell Spin)."""
    try:
        log.info(f"🎲 Opening {name} page...")
        await page.goto(url)
        try:
            await page.wait_for_selector("div.css-mi8v6c", timeout=timeout)
            log.success(f"✅ {name} page loaded")
        except Exception as exc:  # noqa: BLE001
            log.error(f"Error loading {name}", str(exc))
            return False

        log.info("⚙️  Configuring parameters...")
        await place_random_bet(page, timeout)

        log.info(f"⚡ Setting multiplier: {multiplier}")
        await page.wait_for_selector('div.css-1ikdrop:has-text("x") input', timeout=timeout)
        field = page.get_by_role("textbox", name="Multiplier")
        await field.wait_for(state="visible", timeout=timeout)
        await field.fill(str(multiplier))

        log.separator()
        log.info(f"📊 {name} config")
        log.detail("Multiplier", str(multiplier))
        return True
    except Exception as exc:  # noqa: BLE001
        log.error(f"Error setting up {name}", str(exc))
        return False


def _parse_balance(text: str) -> float:
    match = re.search(r"\$([\d.]+)", text) if text else None
    return float(match.group(1)) if match else 0.0


async def play_multiplier_game(
    page,
    name: str,
    min_rounds: int,
    max_rounds: int,
    *,
    balance_check_delay: float = 5.0,
    inter_round_delay: tuple[float, float] = DICE_INTER_ROUND_DELAY,
    balance_timeout: int = 30000,
    enable_balance_check: bool = True,
) -> dict[str, Any]:
    """Generic play loop for multiplier games; stops early if balance drops."""
    from luckflow.platform.balance import get_balance_value

    log.info(f"🎲 Starting {name}...")
    if enable_balance_check:
        previous_balance = await get_balance_value(page, timeout=balance_timeout)
        if previous_balance is None:
            log.warning("Could not read start balance")
            previous_balance = "≈$0.00"
        else:
            log.info(f"💰 Start balance: {previous_balance}")
    else:
        previous_balance = "≈$0.00"

    initial_balance = previous_balance
    rounds_played = 0
    total_rounds = random.randint(min_rounds, max_rounds)
    log.info(f"🎯 Planning {total_rounds} rounds")
    log.separator()

    try:
        for round_num in range(1, total_rounds + 1):
            log.info(f"🔄 Round {round_num}/{total_rounds}")
            try:
                log.info("▶️  Clicking Play")
                await page.locator("button.bet-button").click()
                sleep_for = random.uniform(balance_check_delay, balance_check_delay + 3)
                log.info(f"⏰ Waiting {sleep_for:.1f}s before balance check...")
                await asyncio.sleep(sleep_for)

                if enable_balance_check:
                    current_balance = await get_balance_value(page, timeout=balance_timeout)
                    if current_balance is None:
                        log.error("Could not read balance, stopping")
                        break
                    log.info(f"💰 Balance after round: {current_balance}")
                    if current_balance != previous_balance:
                        try:
                            if _parse_balance(current_balance) < _parse_balance(previous_balance):
                                log.info(f"📉 Balance decreased: {previous_balance} → {current_balance}")
                                log.info("🛑 Stopping due to balance drop")
                                break
                        except Exception:  # noqa: BLE001
                            if current_balance < previous_balance:
                                log.info("🛑 Stopping for safety")
                                break
                    previous_balance = current_balance

                rounds_played += 1
                log.success("✅ Round complete")
                await asyncio.sleep(random.uniform(*inter_round_delay))
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
        "planned_rounds": total_rounds,
        "start_balance": initial_balance if enable_balance_check else "untracked",
        "final_balance": final_balance,
        "completion_rate": (rounds_played / total_rounds * 100) if total_rounds else 0,
        "stopped_early": rounds_played < total_rounds,
    }
    log.info(f"📊 {name} stats", f"{rounds_played}/{total_rounds} rounds, final {final_balance}")
    return result
