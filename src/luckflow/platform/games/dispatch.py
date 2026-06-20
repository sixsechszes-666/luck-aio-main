"""Game selection and the volume/dodep orchestration.

Ported from ``execute_game_logic`` / ``execute_game_logic_volumes`` /
``perform_dodep`` in ``luck_games.py``. These operate on the typed
:class:`~luckflow.core.models.AccountResult` (legacy passed a bare dict) and read
worker keys from the :class:`~luckflow.core.models.Account` row.
"""

from __future__ import annotations

import asyncio
import random
import re

from luckflow.blockchain.solana import forward_transaction_chain, reverse_transaction_chain
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.models import Account, AccountResult
from luckflow.platform.games.dice import dice_play, dice_setup
from luckflow.platform.games.hellspin import hell_play, hell_setup
from luckflow.platform.games.limbo import limbo_play, limbo_setup
from luckflow.platform.games.mines import mines_play, mines_setup

_GAME_NAMES = {0: "Mines", 1: "Dice", 2: "Limbo", 3: "Hell Spin"}


def _wallets_log_path():
    return settings.data_dir / "logs" / "wallets.log"


async def execute_game_logic(page, account_stats: AccountResult, index: int) -> None:
    """Pick one game by weighted choice and play a single session."""
    worker_id = account_stats.WORKER_ID
    gamemode = random.choices([0, 1, 2, 3], weights=[45, 20, 20, 15])[0]
    log.info(f"🎮 [{worker_id}] Game mode: {_GAME_NAMES[gamemode]}")

    if gamemode == 0:
        await mines_setup(page)
        result = await mines_play(page)
        if result and result["success_rate"] > 99:
            account_stats.RESULT = f'SUCCESS_MINES_{result["successful_cashouts"]}_ROUNDS'
            log.success(f"✅ [{worker_id}] Mines: clean run")
        else:
            account_stats.RESULT = f'FAILED_MINES_{result.get("successful_cashouts", 0)}_ROUNDS'
            log.error(f"❌ [{worker_id}] Mines: lost")
    elif gamemode == 1:
        if await dice_setup(page):
            result = await dice_play(page)
            account_stats.RESULT = _multiplier_result(worker_id, "DICE", result)
        else:
            account_stats.RESULT = "FAILED_DICE_SETUP"
    elif gamemode == 2:
        if await limbo_setup(page):
            result = await limbo_play(page)
            account_stats.RESULT = _multiplier_result(worker_id, "LIMBO", result)
        else:
            account_stats.RESULT = "FAILED_LIMBO_SETUP"
    elif gamemode == 3:
        if await hell_setup(page):
            result = await hell_play(page)
            account_stats.RESULT = _multiplier_result(worker_id, "Hell_Spin", result)
        else:
            account_stats.RESULT = "FAILED_Hell_Spin_SETUP"


def _multiplier_result(worker_id: str, tag: str, result: dict | None) -> str:
    if not result:
        return f"FAILED_{tag}_SETUP"
    if result["stopped_early"]:
        log.warning(f"⚠️  [{worker_id}] {tag}: stopped due to losses")
        return f'STOPPED_{tag}_{result["rounds_played"]}_ROUNDS'
    log.success(f"✅ [{worker_id}] {tag}: success")
    return f'SUCCESS_{tag}_{result["rounds_played"]}_ROUNDS'


async def perform_dodep(page, row: Account, worker_id: str, gamemode: int) -> tuple[bool, float]:
    """Top up the worker balance on-chain (forward chain), deposit, then reverse."""
    import base58
    from solders.keypair import Keypair  # local: heavy import only needed here

    log.info(f"🔄 [{worker_id}] Starting on-chain top-up due to balance change...")
    try:
        rpc_url = row.get("RPC_URL") or settings.solana.rpc_url
        main_pk = row.get("PRIVATE_KEY_MAIN")
        master_pk = row.get("PRIVATE_KEY_MASTER")
        worker_pk = row.get("PRIVATE_KEY_WORKER")
        row_id = row.get("UD_DIR")
        log_file = _wallets_log_path()

        if not all([main_pk, master_pk, worker_pk]):
            log.error(f"❌ [{worker_id}] Missing keys for top-up")
            return False, 0

        worker_addr = str(Keypair.from_bytes(base58.b58decode(worker_pk)).pubkey())
        main_addr = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())

        forward_amount = round(random.uniform(0.015, 0.02), 4)
        forward_result = await forward_transaction_chain(
            rpc_url=rpc_url, main_private_key=main_pk, master_private_key=master_pk,
            worker_address=worker_addr, row_id=row_id, log_file=log_file,
            num_temp_wallets=settings.solana.num_temp_wallets, amount_in_sol=forward_amount,
            wait_timeout=300, use_master=settings.solana.use_master_wallet,
        )

        if forward_result["status"] != "success":
            log.error(f"❌ [{worker_id}] Forward chain error: {forward_result.get('error')}")
            return False, 0

        await asyncio.sleep(random.uniform(12, 20))
        await page.get_by_role("button", name="Wallet").click()
        await asyncio.sleep(random.uniform(2, 4))
        await page.get_by_role("button", name="Add Funds").click()

        random_amount = random.uniform(0.0015, 0.003)
        input_field = page.locator('.css-1ikdrop input[type="text"]')
        await asyncio.sleep(random.uniform(1, 2))
        await input_field.fill(str(random_amount))
        await asyncio.sleep(random.uniform(1, 2))
        await page.locator('button:has(svg[style*="margin-right: 12px"]):has-text("Add Funds")').nth(1).click()

        context = page.context
        log.info("⏳ Waiting for confirmation window...")
        connection_page = await context.wait_for_event("page", timeout=50_000)
        await connection_page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)
        log.success("✅ Confirming deposit...")
        await connection_page.bring_to_front()
        await connection_page.click("button.btn-primary")
        await asyncio.sleep(random.uniform(5, 10))

        log.info("🔄 Returning to game...")
        await page.bring_to_front()

        reverse_result = await reverse_transaction_chain(
            rpc_url=rpc_url, worker_private_key=worker_pk, master_private_key=master_pk,
            main_address=main_addr, row_id=row_id, log_file=log_file,
            num_temp_wallets=settings.solana.num_temp_wallets, wait_timeout=300,
            use_master=settings.solana.use_master_wallet,
        )
        if reverse_result["status"] == "success":
            log.success(f"✅ [{worker_id}] Top-up complete (deposited {random_amount} SOL)")
            return True, random_amount
        log.error(f"❌ [{worker_id}] Reverse chain error: {reverse_result.get('error')}")
        return False, random_amount
    except Exception as exc:  # noqa: BLE001
        log.error(f"❌ [{worker_id}] Top-up error", str(exc))
        return False, 0


def _parse_balance(value) -> float:
    if not value or str(value) in ("untracked", "unknown", "unavailable"):
        return 0.0
    match = re.search(r"\$?([\d.,]+)", str(value))
    return float(match.group(1).replace(",", ".")) if match else 0.0


async def execute_game_logic_volumes(
    page, account_stats: AccountResult, index: int, row: Account | None = None
) -> None:
    """Play 10–15 rounds spread across 1–4 random game modes, topping up as needed."""
    worker_id = account_stats.WORKER_ID
    target_rounds_total = random.randint(10, 15)
    num_modes = random.randint(1, 4)
    gamemodes = random.sample([0, 1, 2, 3], num_modes)

    rounds_per_mode = []
    remaining_total = target_rounds_total
    for i in range(num_modes):
        if i == num_modes - 1:
            rounds_per_mode.append(remaining_total)
        else:
            max_rounds = max(1, remaining_total - (num_modes - 1 - i))
            rounds = random.randint(1, max_rounds)
            rounds_per_mode.append(rounds)
            remaining_total -= rounds

    log.info(
        f"🎮 [{worker_id}] {num_modes} random modes; account target {target_rounds_total} rounds"
    )

    for idx, gamemode in enumerate(gamemodes):
        game_name = _GAME_NAMES[gamemode]
        target_rounds = rounds_per_mode[idx]
        rounds_played_total = 0
        log.info(f"🎮 [{worker_id}] Mode {idx + 1}/{num_modes}: {game_name}, target {target_rounds}")

        while rounds_played_total < target_rounds:
            remaining_rounds = target_rounds - rounds_played_total
            result = None
            if gamemode == 0:
                setup_ok = await mines_setup(page)
                if setup_ok:
                    result = await mines_play(page, min_rounds=remaining_rounds, max_rounds=remaining_rounds)
            elif gamemode == 1:
                setup_ok = await dice_setup(page)
                if setup_ok:
                    result = await dice_play(page, min_rounds=remaining_rounds, max_rounds=remaining_rounds)
            elif gamemode == 2:
                setup_ok = await limbo_setup(page)
                if setup_ok:
                    result = await limbo_play(page, min_rounds=remaining_rounds, max_rounds=remaining_rounds)
            else:
                setup_ok = await hell_setup(page)
                if setup_ok:
                    result = await hell_play(page, min_rounds=remaining_rounds, max_rounds=remaining_rounds)

            if not setup_ok:
                log.error(f"❌ [{worker_id}] Could not set up {game_name}")
                break
            if not result:
                log.error(f"❌ [{worker_id}] Error during {game_name}")
                break

            rounds_played = result.get("rounds_played", 0)
            rounds_played_total += rounds_played
            stopped_early = result.get("stopped_early", rounds_played < remaining_rounds)
            if not stopped_early:
                continue

            log.warning(
                f"⚠️  [{worker_id}] {game_name}: stopped ({rounds_played_total}/{target_rounds})"
            )
            balance_dropped_enough = _should_topup(worker_id, result)

            if row is not None and balance_dropped_enough:
                dodep_success, dodep_sol = await perform_dodep(page, row, worker_id, gamemode)
                if dodep_success:
                    account_stats.DODEP_SOL = (account_stats.DODEP_SOL or 0.0) + dodep_sol
                    _accrue_dodep_usd(account_stats, dodep_sol, worker_id)
                else:
                    log.warning(f"⚠️ [{worker_id}] Top-up failed, skipping remaining {game_name} rounds")
                    break
            elif row is None:
                log.warning(f"⚠️ [{worker_id}] No row passed, top-up impossible")
                break
            else:
                log.info(f"👍 [{worker_id}] Continuing without top-up (drop <= 2 cents)")
                break

        log.success(f"✅ [{worker_id}] {game_name} volume done ({rounds_played_total}/{target_rounds})")

    account_stats.RESULT = "SUCCESS_VOLUMES_ALL_MODES"


def _should_topup(worker_id: str, result: dict) -> bool:
    if "start_balance" not in result or "final_balance" not in result:
        return True
    try:
        init_num = _parse_balance(result["start_balance"])
        final_num = _parse_balance(result["final_balance"])
        if init_num - final_num > 0.02:
            log.info(f"📉 [{worker_id}] Balance dropped ${init_num - final_num:.2f} (> 0.02) — top-up needed")
            return True
        if final_num < 0.11:
            log.info(f"📉 [{worker_id}] Final balance below $0.11 (${final_num:.2f}) — top-up needed")
            return True
        log.info(f"📊 [{worker_id}] Drop ${init_num - final_num:.2f} small, final >= $0.11 — top-up skipped")
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning(f"⚠️ [{worker_id}] Error checking balance drop: {exc}. Topping up by default.")
        return True


def _accrue_dodep_usd(account_stats: AccountResult, dodep_sol: float, worker_id: str) -> None:
    start_bal = account_stats.START_BALANCE
    start_sol = account_stats.START_SOL_BALANCE
    if start_bal is None or start_sol is None or float(start_sol) <= 0:
        return
    try:
        rate = float(str(start_bal).replace(",", ".")) / float(start_sol)
        account_stats.DODEP_USD = (account_stats.DODEP_USD or 0.0) + dodep_sol * rate
    except Exception as exc:  # noqa: BLE001
        log.warning(f"⚠️ [{worker_id}] Error computing DODEP_USD: {exc}")
