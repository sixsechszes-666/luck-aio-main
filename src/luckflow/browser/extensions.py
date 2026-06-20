"""Rabby browser-extension automation.

Ported from ``func/rabby.py``. These helpers drive the Rabby Chrome extension's
onboarding flow to import a private key. Selectors, waits and the extension URL
are preserved exactly from the legacy implementation.

The extension onboarding password was a hardcoded literal in the legacy code.
To avoid baking a secret into the source it is now an explicit parameter the
caller must supply.
"""

from __future__ import annotations

import asyncio

from luckflow.core import logging as log


async def find_ext(context) -> str:
    """Wait for the extension page to open and return its extension id."""
    try:
        # Wait for the new page event and grab the Page object.
        page = await context.wait_for_event("page", timeout=10000)
        await page.wait_for_load_state("domcontentloaded")
        extension_url = page.url
        # Extract the extension id from the chrome-extension:// URL.
        extension_id = extension_url.split("/")[2]
    except Exception as exc:
        log.error("Error while waiting for extension page", str(exc))
        raise
    await context.clear_cookies()
    return extension_id


async def imp_rabby(
    context,
    extension_id: str,
    page,
    private_key: str,
    wallet_password: str,
) -> None:
    """Import ``private_key`` into the Rabby extension via its onboarding UI.

    ``wallet_password`` is the local Rabby password used to encrypt the wallet.
    """
    await page.goto(
        f"chrome-extension://{extension_id}/popup.8e8f209b.html"
        "?windowType=tab&appMode=onboarding#/onboarding"
    )
    await page.wait_for_load_state("networkidle")
    pages = context.pages
    for p in pages:
        if p != page:
            await p.close()
    await page.get_by_role("link", name="Import Existing Wallet Import").click()
    await asyncio.sleep(3)
    await page.get_by_role("link", name="Import Private Key").click()
    await asyncio.sleep(3)
    await page.get_by_placeholder("Private key").fill(private_key)
    await asyncio.sleep(3)
    await page.get_by_role("button", name="Import wallet").click()
    await asyncio.sleep(3)
    await page.get_by_placeholder("at least 6 characters").fill(wallet_password)
    await asyncio.sleep(3)
    await page.get_by_role("button", name="Confirm Password").click()
    await asyncio.sleep(3)
    await page.get_by_placeholder("re-enter password").fill(wallet_password)
    await asyncio.sleep(3)
    await page.get_by_role("button", name="Set Password").click()
