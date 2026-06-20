"""Renew Play Timer: detect the on-site button and fund it via an on-chain chain.

Ported from ``check_and_renew_playtimer`` (was in ``luck_warmup_volume_bonuses.py``).
Shared by the daily, warmup-volume and standalone renew workflows.
"""

from __future__ import annotations

import asyncio
import random

import base58
from solders.keypair import Keypair

from luckflow.blockchain.solana import forward_transaction_chain, reverse_transaction_chain
from luckflow.browser.session import safe_click
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account


def _wallets_log_path():
    return settings.data_dir / "logs" / "wallets.log"


async def check_and_renew_playtimer(page, row: Account, worker_id: str, context) -> bool:
    """Renew the play timer if its button is present.

    Returns ``True`` if renewed or the button is absent (safe to continue),
    ``False`` on a critical error.
    """
    try:
        button = await page.query_selector("button.css-1ex6wv0")
        if not button or (await button.inner_text()).strip() != "Renew Play Timer":
            log.step(worker_id, "ℹ️ ", "Renew Play Timer button not found, continuing")
            return True

        log.step(worker_id, "🔄", "Starting on-chain Renew Play Timer...")
        rpc_url = row.get("RPC_URL") or settings.solana.rpc_url
        main_pk = row.get("PRIVATE_KEY_MAIN")
        master_pk = row.get("PRIVATE_KEY_MASTER")
        worker_pk = row.get("PRIVATE_KEY_WORKER")
        wallet_address = row.get("WALLET_ADDRESS") or row.get("EXTERNAL_WALLET")
        row_id = row.get("UD_DIR")
        log_file = _wallets_log_path()

        if not all([main_pk, master_pk, worker_pk, wallet_address]):
            log.step(worker_id, "❌", "Missing keys or wallet for renew")
            return False

        main_address = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())
        random_amount = random.uniform(0.015, 0.025)

        forward_result = await forward_transaction_chain(
            rpc_url=rpc_url, main_private_key=main_pk, master_private_key=master_pk,
            worker_address=wallet_address, row_id=row_id, log_file=log_file,
            num_temp_wallets=settings.solana.num_temp_wallets, amount_in_sol=random_amount,
            wait_timeout=300, use_master=settings.solana.use_master_wallet,
        )
        if forward_result["status"] != "success":
            log.step(worker_id, "❌", f"Forward chain error: {forward_result.get('error')}")
            return False

        await asyncio.sleep(15)
        log.step(worker_id, "⏳", "Clicking Renew buttons...")
        await safe_click(page.locator('button.css-1ex6wv0:has-text("Renew Play Timer")'))
        await asyncio.sleep(1)
        await safe_click(
            page.locator('button.css-1ex6wv0[style*="width: 100%"]:has-text("Renew Play Timer")')
        )

        if context is None:
            context = page.context

        try:
            log.info(f"[{worker_id}] Waiting for wallet confirmation window...")
            connection_page = await context.wait_for_event("page", timeout=50_000)
            await connection_page.wait_for_load_state("domcontentloaded")
            try:
                await connection_page.locator('button:has-text("I trust this site")').click(timeout=3000)
            except Exception:  # noqa: BLE001
                pass
            await connection_page.bring_to_front()
            await connection_page.click("button.btn-primary")
            log.success("✅ Confirming renew deposit...")
        except Exception as confirm_exc:  # noqa: BLE001
            log.warning(f"[{worker_id}] Confirm warning: {confirm_exc}")
            return False

        await asyncio.sleep(10)
        log.step(worker_id, "🔄", "Returning funds (reverse chain)...")
        reverse_result = await reverse_transaction_chain(
            rpc_url=rpc_url, worker_private_key=worker_pk, master_private_key=master_pk,
            main_address=main_address, row_id=row_id, log_file=log_file,
            num_temp_wallets=settings.solana.num_temp_wallets, wait_timeout=300,
            use_master=settings.solana.use_master_wallet,
        )
        if reverse_result["status"] == "success":
            log.step(worker_id, "✅", "Renew Play Timer complete")
            await page.bring_to_front()
            return True
        log.step(worker_id, "❌", f"Reverse error: {reverse_result.get('error')}")
        return False
    except Exception as exc:  # noqa: BLE001
        log.error(f"[{worker_id}] check_and_renew_playtimer error", str(exc))
        return False
