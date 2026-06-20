"""ixBrowser profile lifecycle: launch, attach over CDP, stop, clean up.

Ported from ``func/play.py``. The retry logic, CDP-connect behaviour, timeouts
and context/page selection are preserved exactly; only logging and config access
were modernised (``settings.browser.*`` instead of ``config.Browser``).
"""

from __future__ import annotations

import asyncio

import requests
from ixbrowser_local_api import IXBrowserClient
from patchright.async_api import Browser, Page, Playwright, async_playwright

from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.exceptions import BrowserLaunchError


async def launch_ixbrowser_profile(
    profile_id: int,
    max_retries: int | None = None,
    retry_delay: int | None = None,
) -> tuple[Playwright, Browser, Page, IXBrowserClient]:
    """Launch an ixBrowser profile and attach Playwright to it over CDP.

    Transient errors ("Server busy", "Read timed out", "Bad Gateway") are retried
    ``max_retries`` times with ``retry_delay`` seconds between attempts.
    """
    max_retries = max_retries if max_retries is not None else settings.browser.max_retries
    retry_delay = retry_delay if retry_delay is not None else settings.browser.retry_delay

    playwright: Playwright | None = None
    browser: Browser | None = None
    client: IXBrowserClient | None = None
    loop = asyncio.get_running_loop()

    try:
        client = IXBrowserClient()

        open_result = None
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                log.step(str(profile_id), "🎯", f"Launch attempt #{attempt + 1}/{max_retries}")

                open_result = await loop.run_in_executor(
                    None,
                    lambda: client.open_profile(
                        profile_id=profile_id,
                        cookies_backup=False,
                        load_profile_info_page=False,
                        load_extensions=True,
                    ),
                )

                if not open_result or "debugging_address" not in open_result:
                    error_message = client.message or "No response from server."
                    transient = (
                        "Server busy",
                        "Read timed out",
                        "The returned",
                        "Bad Gateway",
                        "502",
                    )
                    if any(token in error_message for token in transient):
                        raise ConnectionRefusedError(error_message)
                    raise ConnectionError(f"Failed to launch profile. Response: {error_message}")

                log.step(str(profile_id), "✓ ", "Profile launched")
                break

            except ConnectionRefusedError as exc:
                last_exception = exc
                log.step(str(profile_id), "⚠️ ", "Transient launch error", str(exc))
                if attempt < max_retries - 1:
                    log.step(str(profile_id), "⏳", f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    log.step(str(profile_id), "❌", "Launch retries exhausted")
                    raise

        if not open_result:
            raise BrowserLaunchError(
                f"[{profile_id}] Failed to launch profile after {max_retries} attempts"
            ) from last_exception

        debugging_address = open_result.get("debugging_address")

        playwright = await async_playwright().start()
        for attempt in range(5):
            try:
                browser = await playwright.chromium.connect_over_cdp(f"http://{debugging_address}")
                log.step(str(profile_id), "✓ ", "Connected to browser via CDP")
                break
            except Exception as exc:
                if attempt < 4:
                    await asyncio.sleep(5)
                else:
                    raise BrowserLaunchError(
                        f"[{profile_id}] Could not connect to browser after 5 attempts"
                    ) from exc

        assert browser is not None
        if not browser.contexts:
            await browser.wait_for_event("contexts", timeout=15000)

        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        log.step(str(profile_id), "✓ ", "Profile ready")
        return playwright, browser, page, client

    except Exception as exc:
        log.step(str(profile_id), "❌", "Critical launch error", str(exc))
        if browser and browser.is_connected():
            await browser.close()
        if playwright:
            await playwright.stop()
        raise


IXBROWSER_LOCAL_API = "http://127.0.0.1:53200/api/v2"


async def clear_profile_cache(profile_id: int, worker_id: str = "") -> bool:
    """Clear a profile's cache via the ixBrowser local API."""
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{IXBROWSER_LOCAL_API}/profile-clear-cache",
                json={"profile_id": [profile_id]},
                timeout=15,
            ),
        )
        data = response.json()
        if data.get("error", {}).get("code") == 0:
            log.step(worker_id or str(profile_id), "✅", f"Cache cleared (profile_id={profile_id})")
            return True
        message = data.get("error", {}).get("message", "unknown error")
        log.step(worker_id or str(profile_id), "⚠️ ", f"Cache clear error: {message}")
        return False
    except Exception as exc:  # noqa: BLE001
        log.step(worker_id or str(profile_id), "⚠️ ", f"Cache clear request error: {exc}")
        return False


def get_available_tabs(debugging_address: str) -> list:
    """Return the list of CDP tabs exposed by the browser (``/json`` endpoint)."""
    try:
        response = requests.get(f"http://{debugging_address}/json", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Error getting tabs", str(exc))
    return []


def create_new_tab(debugging_address: str) -> dict | None:
    """Create a new tab via the CDP HTTP API (``/json/new``)."""
    try:
        response = requests.post(f"http://{debugging_address}/json/new", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Error creating new tab", str(exc))
    return None


def find_websocket_endpoint(debugging_address: str) -> str | None:
    """Find a usable CDP WebSocket endpoint for the given debugging address."""
    base_url = f"http://{debugging_address}"
    try:
        response = requests.get(f"{base_url}/json", timeout=5)
        if response.status_code == 200:
            tabs_info = response.json()
            for tab in tabs_info:
                ws_url = tab.get("webSocketDebuggerUrl")
                if ws_url:
                    return ws_url
            if tabs_info:
                tab_id = tabs_info[0].get("id")
                if tab_id:
                    return f"ws://{debugging_address}/devtools/page/{tab_id}"

        for path in (
            f"ws://{debugging_address}/devtools/browser",
            f"ws://{debugging_address}/",
            f"ws://{debugging_address}",
        ):
            try:
                test_url = path.replace("ws://", "http://").replace(
                    "/devtools/browser", "/json/version"
                )
                if requests.get(test_url, timeout=1).status_code == 200:
                    return path
            except Exception:  # noqa: BLE001
                continue
    except Exception as exc:  # noqa: BLE001
        log.warning("Error finding WebSocket endpoint", str(exc))
    return None


async def stop_ixbrowser_profile(profile_id: int, client: IXBrowserClient) -> None:
    """Close an ixBrowser profile."""
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, client.close_profile, profile_id)
        if result is None:
            log.warning("Failed to stop profile", str(client.message))
    except Exception as exc:  # noqa: BLE001
        log.warning("Error stopping profile", str(exc))


async def clear_pages(context, page) -> None:
    """Close every tab in ``context`` except ``page``."""
    if context is None:
        return
    for p in context.pages:
        if p != page:
            await p.close()


async def cleanup_browser_resources(
    page,
    browser,
    playwright,
    client,
    profile_id,
    worker_id: str = "",
) -> None:
    """Tear down page → browser → playwright → ixBrowser profile, in order.

    Every step is best-effort: a failure to close one resource never prevents
    the others from being released.
    """
    try:
        if page:
            try:
                await page.close()
            except Exception as exc:  # noqa: BLE001
                log.warning(f"{worker_id} Error closing page", str(exc))
        if browser:
            try:
                await browser.close()
            except Exception as exc:  # noqa: BLE001
                log.warning(f"{worker_id} Error closing browser", str(exc))
        if playwright:
            try:
                await playwright.stop()
            except Exception as exc:  # noqa: BLE001
                log.warning(f"{worker_id} Error stopping playwright", str(exc))
        if client and profile_id:
            try:
                await stop_ixbrowser_profile(profile_id, client)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"{worker_id} Error closing ixBrowser profile", str(exc))
        await asyncio.sleep(0.5)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"{worker_id} Critical error during resource cleanup", str(exc))
