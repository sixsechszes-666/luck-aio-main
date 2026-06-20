"""Wallet connection, account preparation and warm-up flows.

Ported from the connection/account half of ``projects/luck_wallet.py``. Selectors,
timeouts and retry counts are preserved exactly. The Solflare unlock password and
the return-wallet address now come from ``settings.solflare.*``.
"""

from __future__ import annotations

import asyncio
import random

from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.platform.balance import get_balance_value


async def connect_wallet(page) -> None:
    """Connect the Solflare wallet for regular (daily) operation."""
    log.info("💳 Connecting wallet...")
    try:
        log.info("🔌 Clicking Connect...")
        for _ in range(2):
            try:
                await page.locator("button:has-text('Connect')").click()
                break
            except Exception:  # noqa: BLE001
                await page.click('button:has-text("Do Nothing")', timeout=1000)
                continue
        await asyncio.sleep(random.uniform(1, 3))
        log.info("✅ Confirming agreement...")
        await page.locator("label:has-text('I confirm that I have read')").click()
        await asyncio.sleep(random.uniform(1, 3))
        await page.locator("button:has-text('Connect')").nth(1).click()
        await asyncio.sleep(random.uniform(1, 3))

        log.info("🦊 Selecting Solflare...")
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=1000)
        except Exception:  # noqa: BLE001
            log.warning("Solflare button not found")

        log.info("⏳ Waiting for connection window...")
        context = page.context
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")

        log.info("🔓 Unlocking wallet...")
        await connection_page.bring_to_front()
        await connection_page.locator("input[data-testid='input-password']").fill(settings.solflare.password)
        await asyncio.sleep(0.3)
        await connection_page.locator("button[data-testid='btn-unlock']:has-text('Unlock')").click()

        try:
            log.info("⏳ Waiting for confirmation window...")
            connection_page = await context.wait_for_event("page", timeout=3_000)
            await connection_page.wait_for_load_state("domcontentloaded")
        except Exception:  # noqa: BLE001
            await page.locator("button:has-text('Connect')").nth(1).click()
            try:
                connection_page = await context.wait_for_event("page", timeout=5_000)
                await connection_page.wait_for_load_state("domcontentloaded")
            except Exception:  # noqa: BLE001
                log.info("🦊 Selecting Solflare...")
                try:
                    await page.locator("button:has-text('Solflare')").click(timeout=1_000)
                except Exception:  # noqa: BLE001
                    log.warning("Solflare button not found")
                connection_page = await context.wait_for_event("page", timeout=5_000)
                await connection_page.wait_for_load_state("domcontentloaded")

        log.success("✅ Confirming connection...")
        await connection_page.bring_to_front()
        try:
            await connection_page.locator('button:has-text("I trust this site")').click(timeout=3000)
        except Exception:  # noqa: BLE001
            pass
        await connection_page.click("button.btn-primary", timeout=20_000)
        log.success("✅ Wallet connected")
    except Exception as exc:  # noqa: BLE001
        log.error("Wallet connection error", str(exc))
        raise


async def connect_wallet_renew(page) -> None:
    """Connect the wallet for the renew-timer flow."""
    log.info("💳 Connecting wallet...")
    try:
        log.info("🔌 Clicking Connect...")
        await page.locator("button:has-text('Connect')").click()
        log.info("✅ Confirming agreement...")
        await page.locator("label:has-text('I confirm that I have read')").click()
        await page.locator("button:has-text('Connect')").nth(1).click()

        log.info("🦊 Selecting Solflare...")
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=2000)
        except Exception:  # noqa: BLE001
            log.warning("Solflare button not found")

        log.info("⏳ Waiting for connection window...")
        context = page.context
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")

        log.info("🔓 Unlocking wallet...")
        await connection_page.bring_to_front()
        await connection_page.locator("input[data-testid='input-password']").fill(settings.solflare.password)
        await asyncio.sleep(0.3)
        await connection_page.locator("button[data-testid='btn-unlock']:has-text('Unlock')").click()

        await page.locator("button:has-text('Connect')").nth(1).click()
        log.info("🦊 Selecting Solflare...")
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=2000)
        except Exception:  # noqa: BLE001
            log.warning("Solflare button not found")

        log.info("⏳ Waiting for confirmation window...")
        connection_page = await context.wait_for_event("page", timeout=60_000)
        await connection_page.wait_for_load_state("domcontentloaded")

        log.success("✅ Confirming connection...")
        await connection_page.bring_to_front()
        try:
            await page.locator('button:has-text("I trust this site")').click(timeout=3000)
        except Exception:  # noqa: BLE001
            pass
        await connection_page.click("button.btn-primary")
        log.success("✅ Wallet connected")
    except Exception as exc:  # noqa: BLE001
        log.error("Wallet connection error", str(exc))
        raise


async def connect_wallet_withdraw(page) -> None:
    """Connect the wallet for the withdraw flow (wallet-adapter trigger)."""
    log.info("💳 Connecting wallet...")
    for _ in range(5):
        try:
            log.info("🔌 Clicking Connect...")
            try:
                await page.click('button:has-text("Do Nothing")', timeout=3000)
            except Exception:  # noqa: BLE001
                pass
            await page.click(".wallet-adapter-button.wallet-adapter-button-trigger", timeout=60_000)

            log.info("🦊 Selecting Solflare...")
            try:
                await page.locator("button:has-text('Solflare')").click(timeout=5000)
            except Exception:  # noqa: BLE001
                log.warning("Solflare button not found")

            log.info("⏳ Waiting for connection window...")
            context = page.context
            connection_page = await context.wait_for_event("page", timeout=20_000)
            await connection_page.wait_for_load_state("domcontentloaded")

            log.info("🔓 Unlocking wallet...")
            await connection_page.bring_to_front()
            await asyncio.sleep(1)
            await connection_page.locator("input[data-testid='input-password']").fill(settings.solflare.password)
            await asyncio.sleep(1)
            await connection_page.locator("button[data-testid='btn-unlock']:has-text('Unlock')").click()
            log.success("✅ Wallet connected")
            break
        except Exception as exc:  # noqa: BLE001
            await page.goto("https://luck.io/")
            log.error("Wallet connection error", str(exc))
            continue


async def connect_wallet_registration(page) -> None:
    """Connect the wallet during account registration."""
    log.info("📝 Connecting wallet for registration...")
    try:
        for _ in range(20):
            try:
                log.info("🔌 Connection procedure...")
                await page.locator("button:has-text('Connect')").click(timeout=30000)
                break
            except Exception:  # noqa: BLE001
                await page.goto("https://luck.io")
                continue

        await page.locator("label:has-text('I confirm that I have read')").click()
        await page.locator("button:has-text('Connect')").nth(1).click()
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=2000)
        except Exception:  # noqa: BLE001
            log.warning("Solflare not found")

        log.info("⏳ Handling wallet windows...")
        context = page.context
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)

        await connection_page.bring_to_front()
        await asyncio.sleep(1)
        await connection_page.locator("input[data-testid='input-password']").fill(settings.solflare.password)
        await asyncio.sleep(1)
        await connection_page.locator("button[data-testid='btn-unlock']:has-text('Unlock')").click()
        await asyncio.sleep(1)

        try:
            await connection_page.get_by_test_id("btn-accept_terms").click(timeout=3000)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(random.uniform(1, 2))
        try:
            await connection_page.click("button.btn-primary", timeout=1000)
        except Exception:  # noqa: BLE001
            log.warning("First confirmation skipped")

        log.info("⏳ Final confirmation...")
        for _ in range(5):
            try:
                connection_page = await context.wait_for_event("page", timeout=20_000)
                await connection_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)
                await connection_page.bring_to_front()
                await connection_page.click("button.btn-primary")
                break
            except Exception:  # noqa: BLE001
                try:
                    await page.locator("button:has-text('Login')").nth(1).click()
                except Exception:  # noqa: BLE001
                    pass
                continue
        log.success("✅ Registration wallet connected")
    except Exception as exc:  # noqa: BLE001
        log.error("Wallet connection error (registration)", str(exc))
        raise


async def wallet_connect_session(page) -> str | None:
    """Connect using a saved session. Returns ``CONNECTED`` / ``SKIPPED`` / ``None``."""
    try:
        log.info("✅ Connecting wallet (saved session)")
        btn = page.locator("button.wallet-adapter-button.wallet-adapter-button-trigger")
        try:
            await btn.wait_for(state="visible", timeout=3000)
            await btn.click(timeout=3000)
        except Exception:  # noqa: BLE001
            log.info("Wallet button not found, skipping...")
            return "SKIPPED"

        log.info("🦊 Selecting Solflare...")
        try:
            await page.locator("button:has-text('Solflare')").click(timeout=1000)
        except Exception:  # noqa: BLE001
            log.warning("Solflare button not found")

        log.info("⏳ Waiting for connection window...")
        context = page.context
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")

        log.info("🔓 Unlocking wallet...")
        await connection_page.bring_to_front()
        await connection_page.locator("input[data-testid='input-password']").fill(settings.solflare.password)
        await asyncio.sleep(0.3)
        await connection_page.locator("button[data-testid='btn-unlock']:has-text('Unlock')").click()
        log.success("✅ Wallet connected (saved session)")
        return "CONNECTED"
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Saved-session connection error: {exc}")
        return None


async def send_money_back(page) -> None:
    """Return all funds from the Solflare wallet to the configured return address."""
    log.info("💸 Returning funds...")
    try:
        log.info("🌐 Opening wallet...")
        await page.goto("chrome-extension://fbbdmcaopoicabppieiajngpnkjdjlik/wallet.html#/portfolio")
        await asyncio.sleep(3)
        try:
            await page.get_by_test_id("icon-btn-whats-new-modal-close").click(timeout=5_000)
        except Exception:  # noqa: BLE001
            pass

        log.info("📤 Clicking Send...")
        await page.click('button:has-text("Send")')
        log.info("📝 Filling recipient address...")
        await page.fill('input[data-testid="dd-select-recipient"]', settings.solflare.return_wallet_address)
        await asyncio.sleep(1)
        log.info("💰 Selecting max amount...")
        await page.click('button[data-testid="btn-max"]')
        await asyncio.sleep(1)
        log.success("✅ Sending transaction...")
        await page.click('button[type="submit"][data-testid="btn-send"]')
        log.success("✅ Confirming transaction...")
        await page.wait_for_selector('button[data-testid="btn-confirm"]')
        await page.click('button[data-testid="btn-confirm"]')
        log.success("✅ Funds returned")
    except Exception as exc:  # noqa: BLE001
        log.error("Error returning funds", str(exc))
        raise


async def prepare_account(page) -> None:
    """Activate the Smart Vault and add a small amount of funds."""
    log.info("⚙️  Preparing account...")
    try:
        log.info("🔓 Activating Smart Vault...")
        for _ in range(20):
            try:
                await page.click('button:has-text("Activate Smart Vault")', timeout=60_000)
                break
            except Exception:  # noqa: BLE001
                await page.goto("https://luck.io/")
                try:
                    await page.locator("button:has-text('Activate Wallet')").click(timeout=30_000)
                except Exception:  # noqa: BLE001
                    pass
                continue

        context = page.context
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(random.uniform(3, 5))
        await connection_page.bring_to_front()
        try:
            await page.click('label:has-text("I trust this site")', timeout=1000)
        except Exception:  # noqa: BLE001
            pass
        await connection_page.click("button.btn-primary")

        log.info("💰 Adding funds...")
        await page.click('button.css-1oqonge:has-text("Add Funds")')
        await asyncio.sleep(random.uniform(2, 4))

        random_amount = random.uniform(0.0013, 0.0022)
        formatted_amount = f"{random_amount:.{random.randint(4, 7)}f}"
        log.info("📝 Entering amount", formatted_amount)
        await page.fill('div.css-1ikdrop input[type="text"]', formatted_amount)
        await asyncio.sleep(random.uniform(1, 2))
        await page.click('button.css-1ex6wv0[style="width: 100%;"]:has(svg):has-text("Add Funds")')

        log.success("✅ Confirming add funds...")
        connection_page = await context.wait_for_event("page", timeout=20_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)
        await connection_page.bring_to_front()
        try:
            await page.click('label:has-text("I trust this site")', timeout=1000)
        except Exception:  # noqa: BLE001
            pass
        await connection_page.click("button.btn-primary")
        await asyncio.sleep(5)
        log.success("✅ Account prepared")
    except Exception as exc:  # noqa: BLE001
        log.error("Error preparing account", str(exc))
        raise


async def warm_up(page) -> None:
    """Pre-activate weekly/monthly bonuses by creating a play session."""
    log.info("🚀 Warming up account (session pre-activation)...")
    await asyncio.sleep(random.uniform(1, 2))
    await page.locator("button.css-1wc7o8w").nth(1).click()
    try:
        log.info("🌐 Opening account settings...")
        await page.locator('div.css-1ber6xn:has-text("Play Sessions")').click()
        await asyncio.sleep(random.uniform(1, 2))
        await page.get_by_role("button", name="Create New Session").click()
        await page.get_by_role("button", name="1 week").click()
        choice = random.choice(["1 month"])
        await page.locator(f'div.css-1ber6xn:has-text("{choice}")').click()
        await page.locator("label.css-rlrzva").click()

        if random.random() < 0.5:
            loss_limit = random.randint(1000, 500000)
            max_wagered = random.randint(loss_limit, 999999)
            max_bet = random.randint(loss_limit, 999999)
            min_bet = random.randint(1000, max_bet)
            max_bets = random.randint(1000, 99999)

            for label in (
                "Max Realized Loss ($)",
                "Max Wagered Amount Per Session ($)",
                "Min Bet Size ($)",
                "Max Number of Bets",
                "Max Bet Size ($)",
            ):
                await page.get_by_label(label).fill("")

            independent = [
                (page.get_by_label("Min Bet Size ($)"), str(min_bet)),
                (page.get_by_label("Max Number of Bets"), str(max_bets)),
            ]
            random.shuffle(independent)
            ordered = [
                (page.get_by_label("Max Realized Loss ($)"), str(loss_limit)),
                *independent,
                (page.get_by_label("Max Wagered Amount Per Session ($)"), str(max_wagered)),
                (page.get_by_label("Max Bet Size ($)"), str(max_bet)),
            ]
            for locator, value in ordered:
                await locator.fill(value)

        await asyncio.sleep(random.uniform(1, 2))
        await page.get_by_role("button", name="Create", exact=True).click()

        context = page.context
        connection_page = await context.wait_for_event("page", timeout=60_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        await connection_page.bring_to_front()
        await connection_page.click("button.btn-primary")
        await asyncio.sleep(random.uniform(1, 2))
    except Exception as exc:  # noqa: BLE001
        log.error("Error warming up account", str(exc))
        raise


async def navigate_and_get_balance(page, link: str, account_stats: dict) -> None:
    """Navigate to ``link`` and read the start balance, recovering the account if needed.

    Moved here from the legacy ``luck_browser.py`` because it orchestrates wallet
    connection/preparation/return — keeping :mod:`luckflow.platform.balance` a pure
    set of reads.
    """
    for attempt in range(3):
        try:
            await page.goto(link)
            log.info(f"✓ Page loaded (attempt {attempt + 1})")
            await page.wait_for_selector(".css-1sg2lsz", timeout=40000)

            balance_obtained = False
            for balance_attempt in range(30):
                try:
                    await page.goto("https://luck.io/")
                    price_element = page.locator('.css-1mmloj8 div:has-text("≈$")')
                    await price_element.wait_for(state="visible", timeout=10000)
                    start_balance = await get_balance_value(page, timeout=15000)
                    account_stats["START_BALANCE"] = start_balance
                    log.info("💰 Balance", f"${start_balance}")
                    balance_obtained = True
                    break
                except Exception as exc:  # noqa: BLE001
                    if balance_attempt == 0:
                        log.warning(f"Error reading balance (attempt {balance_attempt + 1})", str(exc))
                        try:
                            await page.click('button:has-text("Do Nothing")', timeout=1000)
                        except Exception:  # noqa: BLE001
                            pass
                        log.info("💳 Connecting wallet...")
                        await connect_wallet_registration(page)
                        log.info("⚙️  Preparing account...")
                        await prepare_account(page)
                        log.info("💸 Returning funds...")
                        await send_money_back(page)
                    else:
                        log.warning(f"Error reading balance (attempt {balance_attempt + 1})", str(exc))
                        continue

            if not balance_obtained:
                log.error("Could not read balance after retries")

            try:
                await page.click('button:has-text("Do Nothing")', timeout=1000)
            except Exception:  # noqa: BLE001
                pass
            return
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Attempt {attempt + 1}", str(exc)[:50])
            if attempt == 2:
                log.error("All attempts exhausted")
                raise
