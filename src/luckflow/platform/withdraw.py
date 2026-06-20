"""Withdrawal primitives: UI transfer-out, and the inline dice-gated withdraw.

Ported from ``withdraw_balance_luck`` (``luck_wallet.py``) and
``luck_withdraw_inline.py``. The standalone batch-withdraw *workflow* lives in
:mod:`luckflow.workflows.withdraw`; this module holds the reusable building
blocks. All thresholds/keep-ranges/dice settings come from ``settings.withdraw``.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
from datetime import datetime
from pathlib import Path

import base58
from solders.keypair import Keypair

from luckflow.blockchain.solana import (
    forward_transaction_chain,
    reverse_transaction_chain,
    wait_and_unwrap_wsol,
    wait_for_stable_balance,
)
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult
from luckflow.platform.balance import get_available_amount

_tracker_lock = threading.Lock()


def _tracker_path() -> Path:
    return settings.data_dir / "withdraw_dice_tracker.json"


def _wallets_log_path() -> Path:
    return settings.data_dir / "logs" / "wallets.log"


def _rpc_url() -> str:
    return settings.solana.helius_rpc_url or settings.solana.rpc_url


# --- UI transfer-out --------------------------------------------------------
async def withdraw_balance_luck(page, amount_to_keep_sol: float = 0.0) -> None:
    """Transfer funds out of the Luck.io Smart Vault, keeping ``amount_to_keep_sol``."""
    await page.goto("https://luck.io/smart-vault")
    await page.get_by_role("button", name="Transfer Funds Out").click()
    await asyncio.sleep(2)

    available_amount = await get_available_amount(page)
    input_field = page.locator('.css-1ikdrop input[type="text"]')
    if available_amount:
        amount_to_withdraw = round(max(0.0, available_amount - amount_to_keep_sol), 6)
        log.info(
            "💰 Withdrawable",
            f"{available_amount} SOL, withdrawing {amount_to_withdraw} (keep ~{amount_to_keep_sol:.6f})",
        )
        await asyncio.sleep(2)
        await input_field.fill(str(amount_to_withdraw))
    else:
        log.warning("Could not read available amount")
        await asyncio.sleep(2)
        await input_field.fill(str(available_amount))

    await asyncio.sleep(2)
    await page.locator(
        'button:has(svg[style*="margin-right: 12px"]):has-text("Transfer Funds Out")'
    ).nth(1).click()

    context = page.context
    log.info("⏳ Waiting for confirmation window...")
    connection_page = await context.wait_for_event("page", timeout=50_000)
    await connection_page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(3)
    log.success("✅ Confirming withdrawal...")
    await connection_page.bring_to_front()
    await connection_page.click("button.btn-primary")
    await asyncio.sleep(10)

    for _ in range(10):
        try:
            await asyncio.sleep(3)
            await page.get_by_role("button", name="Transfer Funds Out").first.click(timeout=5000)
            break
        except Exception:  # noqa: BLE001
            continue

    await asyncio.sleep(2)
    available_amount = await get_available_amount(page)
    if available_amount:
        amount_to_withdraw = round(max(0.0, available_amount - amount_to_keep_sol), 6)
        log.info("💰 Withdrawable", f"{available_amount} SOL, withdrawing {amount_to_withdraw}")
        await asyncio.sleep(2)
        await input_field.fill(str(amount_to_withdraw))
    else:
        log.warning("Could not read available amount")
        await asyncio.sleep(2)
        await input_field.fill(str(available_amount))

    await asyncio.sleep(5)
    await page.locator(
        'button:has(svg[style*="margin-right: 12px"]):has-text("Transfer Funds Out")'
    ).nth(1).click()

    for _ in range(15):
        try:
            log.info("🔄 Waiting for Unwrap button...")
            await page.get_by_role("button", name="Unwrap wSOL").wait_for(state="visible", timeout=10000)
            log.success("✅ Unwrap button appeared")
            await asyncio.sleep(3)
            break
        except Exception:  # noqa: BLE001
            await page.goto("https://luck.io/smart-vault")
            continue


# --- Inline dice-gated withdraw --------------------------------------------
def get_trigger() -> str:
    """Resolve the inline-withdraw trigger point for this account."""
    trigger = settings.withdraw.daily_trigger
    if trigger == "random":
        return random.choice(["after_login", "after_game"])
    return trigger


def _load_tracker() -> dict:
    with _tracker_lock:
        path = _tracker_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}


def _save_tracker(tracker: dict) -> None:
    with _tracker_lock:
        path = _tracker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(tracker, fh, indent=2, ensure_ascii=False)


def _get_dice_count(ud_dir: str) -> int:
    return int(_load_tracker().get(ud_dir, {}).get("dice_count", 1))


def _increment_dice(ud_dir: str, increment: int | str) -> None:
    tracker = _load_tracker()
    entry = tracker.get(ud_dir, {"dice_count": 1, "last_withdraw": None})
    step = random.choice([2, 3]) if increment == "random" else int(increment)
    entry["dice_count"] = int(entry.get("dice_count", 1)) + step
    tracker[ud_dir] = entry
    _save_tracker(tracker)


def _reset_dice(ud_dir: str) -> None:
    tracker = _load_tracker()
    tracker[ud_dir] = {"dice_count": 1, "last_withdraw": datetime.now().strftime("%Y-%m-%d")}
    _save_tracker(tracker)


def _is_valid(value) -> bool:
    return bool(value) and str(value).lower() not in ("nan", "none", "")


async def try_withdraw_in_daily(
    page,
    row: Account,
    worker_id: str,
    current_balance,
    account_stats: AccountResult,
) -> str:
    """Attempt an inline withdrawal inside an open daily session, gated by a dice roll.

    Returns one of: DISABLED | SKIPPED_LOW_BALANCE | DICE_SKIP | SKIPPED_NO_KEYS | SUCCESS | ERROR.
    """
    cfg = settings.withdraw

    def _set_no_withdraw(result: str) -> str:
        account_stats.WITHDRAW_RESULT = result
        account_stats.WITHDRAW_AMOUNT = 0
        account_stats.WITHDRAW_DATE = ""
        return result

    if not cfg.in_daily_enabled:
        return _set_no_withdraw("DISABLED")

    try:
        balance = float(str(current_balance).replace(",", "."))
    except (ValueError, TypeError):
        balance = 0.0

    if balance < cfg.daily_min_balance:
        log.step(worker_id, "💸", f"Inline withdraw: ${balance:.2f} < ${cfg.daily_min_balance:.2f} — skip")
        return _set_no_withdraw("SKIPPED_LOW_BALANCE")

    ud_dir = str(row.get("UD_DIR", "")).strip()
    dice_count = _get_dice_count(ud_dir)
    sides = cfg.dice_sides
    results = [random.randint(1, sides) for _ in range(dice_count)]
    hit = any(r == 1 for r in results)
    log.step(worker_id, "🎲", f"Inline withdraw: {dice_count} dice → {results} → {'HIT' if hit else 'MISS'}")

    if not hit:
        _increment_dice(ud_dir, cfg.dice_increment)
        return _set_no_withdraw("DICE_SKIP")

    pk_main = row.get("PRIVATE_KEY_MAIN")
    pk_master = row.get("PRIVATE_KEY_MASTER")
    pk_worker = row.get("PRIVATE_KEY_WORKER")
    wallet = row.get("WALLET_ADDRESS")
    if not (_is_valid(pk_main) and _is_valid(pk_worker) and _is_valid(wallet)):
        log.warning(f"[{worker_id}] Inline withdraw: missing keys — skip")
        return _set_no_withdraw("SKIPPED_NO_KEYS")

    try:
        profile_id = int(ud_dir)
        keep_amount = round(random.uniform(cfg.keep_min, cfg.keep_max), 4)
        start_sol = account_stats.START_SOL_BALANCE
        start_usd = account_stats.START_BALANCE or balance
        sol_price = (float(start_usd) / start_sol) if (start_sol and start_sol > 0) else 180.0
        amount_to_keep_sol = keep_amount / sol_price
        log.step(worker_id, "💸", f"Inline withdraw: keep ${keep_amount:.4f} (~{amount_to_keep_sol:.6f} SOL)")

        forward_completed = await _run_forward(
            worker_id, pk_main, pk_master if _is_valid(pk_master) else None, pk_worker, profile_id
        )
        await asyncio.sleep(random.uniform(5, 8))

        await withdraw_balance_luck(page, amount_to_keep_sol=amount_to_keep_sol)
        await asyncio.sleep(3)
        await _unwrap_and_settle(worker_id, pk_worker)

        if forward_completed:
            await _run_reverse(
                worker_id, pk_worker, pk_master if _is_valid(pk_master) else None, pk_main, profile_id
            )

        withdraw_amount = round(balance - keep_amount, 4)
        _reset_dice(ud_dir)
        account_stats.WITHDRAW_RESULT = "SUCCESS"
        account_stats.WITHDRAW_AMOUNT = withdraw_amount
        account_stats.WITHDRAW_DATE = datetime.now().strftime("%Y-%m-%d")
        log.success(f"[{worker_id}] Inline withdraw SUCCESS: ~${withdraw_amount:.4f}")
        return "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        log.error(f"[{worker_id}] Inline withdraw ERROR", str(exc))
        return _set_no_withdraw("ERROR")


async def _run_forward(worker_id, pk_main, pk_master, pk_worker, profile_id) -> bool:
    """Run the forward funding chain. Returns True on success."""
    try:
        worker_address = str(Keypair.from_bytes(base58.b58decode(pk_worker)).pubkey())
        forward_amount = round(random.uniform(0.015, 0.025), 4)
        suffix = "" if pk_master else " (no master)"
        log.step(worker_id, "🔄", f"Forward transfer{suffix} ({forward_amount} SOL)...")
        fwd = await forward_transaction_chain(
            rpc_url=_rpc_url(), main_private_key=pk_main, master_private_key=pk_master,
            worker_address=worker_address, row_id=profile_id, log_file=_wallets_log_path(),
            num_temp_wallets=settings.solana.num_temp_wallets, amount_in_sol=forward_amount,
            wait_timeout=300, use_master=bool(pk_master) and settings.solana.use_master_wallet,
        )
        if fwd.get("status") == "success":
            log.step(worker_id, "✓ ", "Forward transfer succeeded")
            return True
        log.error(f"[{worker_id}] Forward transfer error: {fwd.get('error')}")
        return False
    except Exception as exc:  # noqa: BLE001
        log.error(f"[{worker_id}] Forward transfer exception", str(exc))
        return False


async def _unwrap_and_settle(worker_id, pk_worker) -> None:
    try:
        log.step(worker_id, "🔄", "Unwrapping wSOL...")
        unwrap_sig = await wait_and_unwrap_wsol(
            rpc_url=_rpc_url(), owner_private_key_b58=pk_worker, wait_for_funds=True, timeout=300
        )
        log.step(worker_id, "✓ ", f"wSOL unwrapped (sig: {unwrap_sig})")
        worker_address = str(Keypair.from_bytes(base58.b58decode(pk_worker)).pubkey())
        await wait_for_stable_balance(
            rpc_url=_rpc_url(), address=worker_address, poll_interval=0.3, stable_reads=2, timeout=30
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"[{worker_id}] wSOL unwrap error (may be absent): {exc}")


async def _run_reverse(worker_id, pk_worker, pk_master, pk_main, profile_id) -> None:
    try:
        main_address = str(Keypair.from_bytes(base58.b58decode(pk_main)).pubkey())
        log.step(worker_id, "🔄", "Reverse transfer...")
        rev = await reverse_transaction_chain(
            rpc_url=_rpc_url(), worker_private_key=pk_worker, master_private_key=pk_master,
            main_address=main_address, row_id=profile_id, log_file=_wallets_log_path(),
            num_temp_wallets=settings.solana.num_temp_wallets, wait_timeout=300,
            use_master=bool(pk_master) and settings.solana.use_master_wallet,
        )
        if rev.get("status") == "success":
            log.step(worker_id, "✓ ", "Reverse transfer succeeded")
        else:
            log.error(f"[{worker_id}] Reverse transfer error: {rev.get('error')}")
    except Exception as exc:  # noqa: BLE001
        log.error(f"[{worker_id}] Reverse transfer exception", str(exc))
