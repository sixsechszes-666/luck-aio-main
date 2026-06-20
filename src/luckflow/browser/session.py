"""Generic browser-session mechanics: QR-code extraction and decoding.

Split out of the legacy ``luck_browser.py``. These helpers are domain-agnostic
(they decode a QR rendered as an SVG ``<path>``); the Luck.io-specific reads
(balance, chest, login link) live in :mod:`luckflow.platform.balance`.
"""

from __future__ import annotations

import asyncio
import io

import pyzbar.pyzbar as pyzbar
from PIL import Image, ImageDraw

from luckflow.core import logging as log


async def safe_click(locator, retries: int = 3, delay: float = 1) -> None:
    """Click a locator, retrying when the element detaches mid-interaction."""
    for _ in range(retries):
        try:
            await locator.wait_for(state="visible", timeout=5_000)
            await locator.click()
            return
        except Exception as exc:  # noqa: BLE001
            if "detached" in str(exc).lower():
                await asyncio.sleep(delay)
                continue
            raise
    raise RuntimeError("Could not click element")

_QR_SIZE = 49
_QR_SCALE = 10


def decode_qr_from_svg_path(path_data: str) -> str | None:
    """Rasterize a QR ``<path d=...>`` and decode it to its embedded string."""
    img = Image.new("RGB", (_QR_SIZE * _QR_SCALE, _QR_SIZE * _QR_SCALE), "white")
    draw = ImageDraw.Draw(img)

    for segment in path_data.split("M")[1:]:
        parts = segment.strip().split("h")
        if len(parts) < 2:
            continue
        coords = parts[0].replace(",", " ").split()
        if len(coords) < 2:
            continue
        x, y = int(coords[0]), int(coords[1])
        width_part = parts[1].split("v")[0].split("z")[0]
        try:
            width = int(width_part)
        except ValueError:
            width = 1
        draw.rectangle(
            [x * _QR_SCALE, y * _QR_SCALE, (x + width) * _QR_SCALE, (y + 1) * _QR_SCALE],
            fill="black",
        )

    decoded = pyzbar.decode(img)
    return decoded[0].data.decode("utf-8") if decoded else None


async def get_and_decode_qr_code(page) -> str | None:
    """Read the QR ``<path>`` from ``page`` and decode it."""
    try:
        qr_locator = page.locator('path[fill="#000000"]')
        await qr_locator.wait_for(timeout=10000)
        path_data = await qr_locator.get_attribute("d")
        if path_data:
            log.info("QR code found, decoding...")
            return decode_qr_from_svg_path(path_data)
        log.warning("QR path data not found")
        return None
    except Exception as exc:  # noqa: BLE001
        log.error("Error reading QR code", str(exc))
        return None


async def get_and_decode_qr_via_svg(page) -> str | None:
    """Alternative QR decode path that renders a full SVG via cairosvg."""
    import cairosvg  # optional dependency; imported lazily

    try:
        path_data = await page.locator('path[fill="#000000"]').get_attribute("d")
        if not path_data:
            return None
        svg_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<svg width="490" height="490" viewBox="0 0 49 49" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="49" height="49" fill="white"/>'
            f'<path fill="#000000" d="{path_data}" shape-rendering="crispEdges"/></svg>'
        )
        png_data = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
        image = Image.open(io.BytesIO(png_data))
        decoded = pyzbar.decode(image)
        if decoded:
            return decoded[0].data.decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        log.error("Error decoding QR via SVG", str(exc))
    return None


async def find_qr_code_element(page) -> str | None:
    """Locate the QR ``<path d=...>`` attribute trying several selectors."""
    for selector in (
        'path[fill="#000000"]',
        'svg path[d*="M0 0h"]',
        'svg path[shape-rendering="crispEdges"]',
        'path[d^="M0 0h"]',
    ):
        try:
            element = page.locator(selector)
            if await element.count() > 0:
                return await element.first.get_attribute("d")
        except Exception:  # noqa: BLE001
            continue
    return None


async def wait_for_new_qr_code(page, previous_path: str | None = None) -> tuple[str | None, str | None]:
    """Poll until a QR ``<path>`` different from ``previous_path`` appears."""
    for _ in range(30):
        try:
            current_path = await page.locator('path[fill="#000000"]').get_attribute("d")
            if current_path and current_path != previous_path:
                url = decode_qr_from_svg_path(current_path)
                if url:
                    return url, current_path
            await page.wait_for_timeout(1000)
        except Exception:  # noqa: BLE001
            await page.wait_for_timeout(1000)
    return None, None
