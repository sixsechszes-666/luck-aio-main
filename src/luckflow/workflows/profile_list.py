"""Profile-list workflow: collect all ixBrowser profiles into an Excel sheet.

Ported from ``luck_profile_list.py``. Pages through the ixBrowser local API and
writes a flat table; no browsers are launched.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from luckflow.browser.ixbrowser import IXBROWSER_LOCAL_API
from luckflow.config import settings
from luckflow.core import logging as log

COLUMNS = [
    "profile_id", "name", "group_id", "group_name", "tag_id", "tag_name", "note", "color",
    "username", "password", "tfa_secret", "site_url", "proxy_mode", "proxy_id", "proxy_type",
    "proxy_ip", "proxy_port", "real_ip", "proxy_url", "cache_path", "last_open_time",
    "last_open_datetime",
]

PROXY_MODE_MAP = {1: "Personal proxy", 2: "Custom proxy", 3: "No proxy", 4: "URL proxy"}


def _fetch_profile_page(page: int, limit: int = 100) -> dict | None:
    try:
        response = requests.post(
            f"{IXBROWSER_LOCAL_API}/profile-list",
            json={"profile_id": 0, "name": "", "group_id": 0, "tag_id": 0, "page": page, "limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        log.error(f"Profile page {page} request error", str(exc))
        return None


def _fetch_all_profiles(limit: int = 100) -> list[dict]:
    all_profiles: list[dict] = []
    log.info("📡 Requesting first profile page...")
    first = _fetch_profile_page(1, limit)
    if not first or first.get("error", {}).get("code") != 0:
        log.error("Profile list", "API returned no data or an error")
        return []

    data_block = first.get("data", {})
    total = data_block.get("total", 0)
    all_profiles.extend(data_block.get("data", []))
    log.success(f"✓ Total profiles: {total}, fetched: {len(all_profiles)}")
    if total <= limit:
        return all_profiles

    total_pages = (total + limit - 1) // limit
    for p in range(2, total_pages + 1):
        log.info(f"   ↳ Page {p}/{total_pages}...")
        page_data = _fetch_profile_page(p, limit)
        if not page_data or page_data.get("error", {}).get("code") != 0:
            log.warning(f"Skipping page {p}")
            continue
        all_profiles.extend(page_data.get("data", {}).get("data", []))
    log.success(f"✅ Total fetched: {len(all_profiles)} profiles")
    return all_profiles


def _profile_to_row(profile: dict) -> dict:
    last_open = profile.get("last_open_time")
    last_open_dt = None
    if isinstance(last_open, (int, float)) and last_open > 0:
        try:
            last_open_dt = datetime.fromtimestamp(last_open).strftime("%d.%m.%Y %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            last_open_dt = None
    mode_code = profile.get("proxy_mode")
    return {
        **{col: profile.get(col, "") for col in COLUMNS if col not in ("proxy_mode", "last_open_time", "last_open_datetime")},
        "proxy_mode": PROXY_MODE_MAP.get(mode_code, str(mode_code)) if mode_code else "",
        "last_open_time": last_open,
        "last_open_datetime": last_open_dt,
    }


def _save_profiles_to_excel(profiles: list[dict], output_path: str | Path) -> bool:
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame([_profile_to_row(p) for p in profiles], columns=COLUMNS)
        df.to_excel(output_path, index=False)
        log.success(f"💾 Table saved: {output_path}")
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Excel save error", str(exc))
        return False


async def collect_profile_list(output_path: str | Path | None = None) -> list[dict] | None:
    """Fetch all ixBrowser profiles and save them to ``output_path``."""
    output_path = Path(output_path) if output_path else settings.result_dir / "browser_data" / "profile_list.xlsx"
    log.separator()
    log.info("🗂️  Collecting ixBrowser profile data")
    loop = asyncio.get_running_loop()
    profiles = await loop.run_in_executor(None, _fetch_all_profiles)
    if not profiles:
        log.error("No profile data fetched. Is ixBrowser running?")
        return None

    log.info(f"📊 Building table from {len(profiles)} profiles...")
    if await loop.run_in_executor(None, _save_profiles_to_excel, profiles, output_path):
        dated = Path(str(output_path).replace(".xlsx", f"_{datetime.now():%d.%m}.xlsx"))
        await loop.run_in_executor(None, _save_profiles_to_excel, profiles, dated)
    log.success(f"✅ Done. Profiles: {len(profiles)}")
    return profiles
