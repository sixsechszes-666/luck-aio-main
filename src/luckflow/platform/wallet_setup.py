"""One-time browser-extension setup: captcha solver and Solflare wallet import.

Ported from ``setup_captcha`` / ``setup_wallet`` in ``projects/luck_wallet.py``.
The captcha API key and wallet password come from ``settings``.
"""

from __future__ import annotations

import asyncio

from luckflow.config import settings
from luckflow.core import logging as log


async def setup_captcha(page) -> None:
    """Configure the CaptchaFox solver extension with the configured API key."""
    log.info("🤖 Configuring captcha extension...")
    try:
        log.info("🌐 Opening extension settings...")
        await page.goto("chrome-extension://bpkfncdcffafpagihcokeobngeminodd/popup.html")
        log.info("🔑 Entering API key...")
        await page.fill("#client-key-input", settings.captcha.fox_api_key)
        await asyncio.sleep(1)
        log.success("✅ Saving settings...")
        try:
            await page.click('button[type="button"].ant-btn-icon-only', timeout=1000)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(2)
        log.success("✅ Captcha extension configured")
    except Exception as exc:  # noqa: BLE001
        log.error("Error configuring captcha", str(exc))
        raise


async def setup_wallet(page, seed_phrase: str) -> None:
    """Import an existing Solflare wallet from a seed phrase."""
    log.info("💳 Setting up wallet...")
    try:
        for _ in range(5):
            try:
                log.info("🌐 Opening wallet onboarding...")
                await page.goto("chrome-extension://fbbdmcaopoicabppieiajngpnkjdjlik/wallet.html#/onboard")
                log.info("🔄 Restoring existing wallet...")
                await page.get_by_test_id("btn-already-have-wallet").click(timeout=10000)
                break
            except Exception:  # noqa: BLE001
                await page.goto("chrome-extension://bpkfncdcffafpagihcokeobngeminodd/popup.html")
                continue

        log.info("📝 Entering seed phrase...")
        await page.get_by_test_id("input-recovery-phrase-1").fill(seed_phrase)
        await page.get_by_test_id("btn-continue").click()

        log.info("🔒 Setting password...")
        await page.get_by_test_id("input-new-password").fill(settings.solflare.password)
        await page.get_by_test_id("input-repeat-password").fill(settings.solflare.password)
        await page.get_by_test_id("btn-continue").click()

        log.info("⚡ Quick setup...")
        await page.get_by_role("button", name="translate").click()
        await page.get_by_test_id("li-settings-en").click()
        await page.get_by_test_id("btn-quick-setup").click()
        await page.get_by_test_id("btn-explore").click()
        await asyncio.sleep(3)
        log.success("✅ Wallet set up")
    except Exception as exc:  # noqa: BLE001
        log.error("Error setting up wallet", str(exc))
        raise
