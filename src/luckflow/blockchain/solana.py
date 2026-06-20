"""On-chain Solana operations: transfers, wSOL unwrap, temp-wallet chains.

Ported from ``projects/luck_onchain.py``. The RPC behaviour is preserved exactly:
``commitment=Processed`` for fast reads, ``skip_preflight`` per speed mode,
exponential backoff on HTTP 429, blockhash-expiry retries, and the
forward/reverse transaction chains routed through freshly generated temporary
wallets.

Config now comes from ``settings.solana.*`` and the speed mode is resolved at
call time (not import time). The legacy module-level ``main()`` CLI and its
hardcoded Helius URL were dropped.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Finalized, Processed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import transfer
from solders.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import CloseAccountParams, close_account, get_associated_token_address

from luckflow.config import settings
from luckflow.core import logging as log

LAMPORTS_PER_SOL = 1_000_000_000
DEFAULT_TRANSACTION_FEE = 5000
WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

# Speed modes:
#   FAST   — skip_preflight=True,  commitment=Processed (lowest latency)
#   NORMAL — skip_preflight=True,  commitment=Confirmed
#   SAFE   — skip_preflight=False, commitment=Finalized
_TX_OPTS = {
    "FAST": TxOpts(skip_preflight=True, preflight_commitment=Processed),
    "NORMAL": TxOpts(skip_preflight=True, preflight_commitment=Confirmed),
    "SAFE": TxOpts(skip_preflight=False, preflight_commitment=Finalized),
}

_RATE_MARKERS = ("429", "too many requests", "rate limit", "ratelimit")


def _tx_opts() -> TxOpts:
    return _TX_OPTS.get(settings.solana.onchain_speed_mode, _TX_OPTS["FAST"])


def _speed_mode() -> str:
    return settings.solana.onchain_speed_mode


def _balance_check_interval() -> float:
    return settings.solana.onchain_balance_check_interval


def _balance_check_timeout() -> int:
    return settings.solana.onchain_balance_check_timeout


def _max_retries() -> int:
    return settings.solana.onchain_max_retries


def _transaction_delay() -> float:
    return settings.solana.transaction_delay


def _error_log_path() -> Path:
    return settings.data_dir / "logs" / "stuck_wallets.log"


class InsufficientFundsError(Exception):
    pass


class InvalidAmountError(Exception):
    pass


class BalanceTimeoutError(Exception):
    pass


def _is_rate_limit_error(exc: BaseException) -> bool:
    """True if ``exc`` (or any wrapped cause) is an HTTP 429 / rate-limit error."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if any(marker in str(current).lower() for marker in _RATE_MARKERS):
            return True
        response = getattr(current, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            return True
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


async def _send_with_retries(
    client: AsyncClient,
    keypair: Keypair,
    instructions: list,
    *,
    label: str,
    max_retries: int,
) -> str:
    """Send a signed transaction, retrying on 429 and blockhash expiry."""
    for attempt in range(max_retries):
        try:
            blockhash = (await client.get_latest_blockhash()).value.blockhash
            message = Message.new_with_blockhash(instructions, keypair.pubkey(), blockhash)
            transaction = Transaction([keypair], message, blockhash)
            response = await client.send_transaction(transaction, opts=_tx_opts())
            return str(response.value)
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            if _is_rate_limit_error(exc):
                backoff = 2 ** (attempt + 1)
                log.warning(
                    f"Rate limited 429 ({label}, attempt {attempt + 1}/{max_retries})",
                    f"Waiting {backoff}s...",
                )
                if attempt == max_retries - 1:
                    raise ConnectionError(
                        f"{label} failed after {max_retries} attempts (rate limit): {exc}"
                    ) from exc
                await asyncio.sleep(backoff)
            elif "BlockhashNotFound" in error_msg or "Blockhash not found" in error_msg:
                log.warning(f"Blockhash expired ({label}, attempt {attempt + 1}/{max_retries})", "Retrying...")
                if attempt == max_retries - 1:
                    raise ConnectionError(f"{label} blockhash retry failed: {exc}") from exc
                await asyncio.sleep(0.3)
            else:
                raise ConnectionError(f"{label} transaction failed: {exc}") from exc
    raise ConnectionError(f"{label} exhausted retries")  # pragma: no cover


async def wait_for_balance(
    client: AsyncClient,
    wallet_pubkey: Pubkey,
    required_lamports: int,
    timeout: int | None = None,
    check_interval: float | None = None,
) -> int:
    """Block until ``wallet_pubkey`` holds at least ``required_lamports``."""
    timeout = timeout if timeout is not None else _balance_check_timeout()
    check_interval = check_interval if check_interval is not None else _balance_check_interval()
    start = asyncio.get_event_loop().time()

    while True:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            raise BalanceTimeoutError(
                f"Timeout after {timeout}s. Required: {required_lamports / LAMPORTS_PER_SOL:.9f} SOL"
            )
        try:
            current = (await client.get_balance(wallet_pubkey, commitment=Processed)).value
            if current >= required_lamports:
                log.info("Balance received", f"{current / LAMPORTS_PER_SOL:.9f} SOL after {elapsed:.1f}s")
                return current
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(check_interval)


async def send_sol(
    rpc_url: str,
    sender_private_key_b58: str,
    receiver_address: str,
    amount_in_sol: float,
    wait_for_funds: bool = True,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str:
    """Send a fixed ``amount_in_sol`` from sender to receiver."""
    timeout = timeout if timeout is not None else _balance_check_timeout()
    max_retries = max_retries if max_retries is not None else _max_retries()
    if amount_in_sol <= 0:
        raise InvalidAmountError(f"Amount must be positive, got {amount_in_sol}")
    amount_in_lamports = int(amount_in_sol * LAMPORTS_PER_SOL)

    async with AsyncClient(rpc_url) as client:
        try:
            sender = Keypair.from_bytes(base58.b58decode(sender_private_key_b58))
        except Exception as exc:
            raise ValueError(f"Invalid sender private key: {exc}") from exc
        try:
            receiver = Pubkey.from_string(receiver_address)
        except Exception as exc:
            raise ValueError(f"Invalid receiver address: {exc}") from exc

        required = amount_in_lamports + DEFAULT_TRANSACTION_FEE
        try:
            current = (await client.get_balance(sender.pubkey(), commitment=Processed)).value
        except Exception as exc:
            raise ConnectionError(f"Failed to fetch balance: {exc}") from exc

        if current < required:
            if wait_for_funds:
                await wait_for_balance(client, sender.pubkey(), required, timeout)
            else:
                raise InsufficientFundsError(
                    f"Insufficient funds. Required: {required / LAMPORTS_PER_SOL:.9f} SOL, "
                    f"Available: {current / LAMPORTS_PER_SOL:.9f} SOL"
                )

        instruction = transfer(
            {"from_pubkey": sender.pubkey(), "to_pubkey": receiver, "lamports": amount_in_lamports}
        )
        signature = await _send_with_retries(
            client, sender, [instruction], label="SEND", max_retries=max_retries
        )
        log.transaction("SEND", str(sender.pubkey()), receiver_address, amount_in_sol, signature)
        return signature


async def drain_sol_wallet(
    rpc_url: str,
    sender_private_key_b58: str,
    receiver_address: str,
    wait_for_funds: bool = True,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str:
    """Send the entire balance (minus fee) from sender to receiver."""
    timeout = timeout if timeout is not None else _balance_check_timeout()
    max_retries = max_retries if max_retries is not None else _max_retries()

    async with AsyncClient(rpc_url) as client:
        try:
            sender = Keypair.from_bytes(base58.b58decode(sender_private_key_b58))
        except Exception as exc:
            raise ValueError(f"Invalid sender private key: {exc}") from exc
        try:
            receiver = Pubkey.from_string(receiver_address)
        except Exception as exc:
            raise ValueError(f"Invalid receiver address: {exc}") from exc

        start = asyncio.get_event_loop().time()
        current = 0
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                raise BalanceTimeoutError(f"Timeout after {timeout}s waiting for balance")
            try:
                current = (await client.get_balance(sender.pubkey(), commitment=Processed)).value
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.3)
                continue
            if current > DEFAULT_TRANSACTION_FEE * 2:
                break
            if not wait_for_funds and elapsed > 1.0:
                raise InsufficientFundsError("Wallet is empty")
            await asyncio.sleep(_balance_check_interval())

        amount_to_send = current - DEFAULT_TRANSACTION_FEE
        if amount_to_send <= 0:
            raise InsufficientFundsError(
                f"Insufficient funds for fee. Balance: {current / LAMPORTS_PER_SOL:.9f} SOL"
            )

        instruction = transfer(
            {"from_pubkey": sender.pubkey(), "to_pubkey": receiver, "lamports": amount_to_send}
        )
        signature = await _send_with_retries(
            client, sender, [instruction], label="DRAIN", max_retries=max_retries
        )
        log.transaction(
            "DRAIN", str(sender.pubkey()), receiver_address, amount_to_send / LAMPORTS_PER_SOL, signature
        )
        return signature


async def wait_and_unwrap_wsol(
    rpc_url: str,
    owner_private_key_b58: str,
    wait_for_funds: bool = True,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> str:
    """Wait for wSOL to arrive in the owner's ATA, then close it (unwrap)."""
    timeout = timeout if timeout is not None else _balance_check_timeout()
    max_retries = max_retries if max_retries is not None else _max_retries()

    async with AsyncClient(rpc_url) as client:
        try:
            owner = Keypair.from_bytes(base58.b58decode(owner_private_key_b58))
        except Exception as exc:
            raise ValueError(f"Invalid owner private key: {exc}") from exc

        ata = get_associated_token_address(owner.pubkey(), WSOL_MINT)
        start = asyncio.get_event_loop().time()
        wsol_balance = 0.0
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                raise BalanceTimeoutError(f"Timeout after {timeout}s waiting for wSOL")
            try:
                resp = await client.get_token_account_balance(ata, commitment=Processed)
                if resp.value.ui_amount and resp.value.ui_amount > 0:
                    wsol_balance = resp.value.ui_amount
                    log.info("wSOL balance received", f"{wsol_balance} wSOL")
                    break
            except Exception:  # noqa: BLE001
                pass
            if not wait_for_funds and elapsed > 1.0:
                raise InsufficientFundsError("wSOL wallet is empty or not found")
            await asyncio.sleep(_balance_check_interval())

        params = CloseAccountParams(
            program_id=TOKEN_PROGRAM_ID, account=ata, dest=owner.pubkey(), owner=owner.pubkey(), signers=[]
        )
        signature = await _send_with_retries(
            client, owner, [close_account(params)], label="UNWRAP", max_retries=max_retries
        )
        log.transaction("UNWRAP", str(ata), str(owner.pubkey()), wsol_balance, signature)
        return signature


async def wait_for_stable_balance(
    rpc_url: str,
    address: str,
    poll_interval: float = 0.3,
    stable_reads: int = 2,
    timeout: int = 30,
) -> int:
    """Return the balance once it reads identical ``stable_reads`` times in a row."""
    async with AsyncClient(rpc_url) as client:
        pubkey = Pubkey.from_string(address)
        start = asyncio.get_event_loop().time()
        last_balance = -1
        consecutive = 0
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                raise BalanceTimeoutError(
                    f"Timeout after {timeout}s waiting for stable balance on {address[:8]}…"
                )
            try:
                current = (await client.get_balance(pubkey, commitment=Processed)).value
                if current == last_balance and current > 0:
                    consecutive += 1
                    if consecutive >= stable_reads:
                        log.info("Balance stable", f"{current / LAMPORTS_PER_SOL:.9f} SOL after {elapsed:.1f}s")
                        return current
                else:
                    consecutive = 0
                    last_balance = current
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(poll_interval)


def generate_wallet() -> tuple[str, str]:
    """Generate a fresh Solana keypair, returning ``(private_b58, public)``."""
    keypair = Keypair()
    private_key_b58 = base58.b58encode(bytes(keypair)).decode("utf-8")
    return private_key_b58, str(keypair.pubkey())


async def save_wallet_to_log(
    private_key: str, public_key: str, row_id: Any, wallet_type: str, log_file: Path
) -> None:
    """Append a temporary wallet's keypair to the run log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] Row_{row_id} | Type: {wallet_type} | Private: {private_key} | Public: {public_key}\n"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    async with asyncio.Lock():
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(entry)


async def save_stuck_wallet_to_error_log(
    private_key: str, public_key: str, row_id: Any, step: str, error: str, log_file: Path | None = None
) -> None:
    """Append a wallet that got stuck mid-chain to the error log (funds may remain)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] Row_{row_id} | Step: {step} | Private: {private_key} | "
        f"Public: {public_key} | Error: {error[:120]}\n"
    )
    error_log = _error_log_path()
    error_log.parent.mkdir(parents=True, exist_ok=True)
    async with asyncio.Lock():
        with open(error_log, "a", encoding="utf-8") as fh:
            fh.write(entry)
    log.warning("STUCK WALLET LOGGED", f"Row_{row_id} @ {step} → {public_key[:8]}...{public_key[-4:]}")


async def forward_transaction_chain(
    rpc_url: str,
    main_private_key: str,
    master_private_key: str,
    worker_address: str,
    row_id: Any,
    log_file: Path,
    num_temp_wallets: int = 1,
    amount_in_sol: float = 0.015,
    wait_timeout: int | None = None,
    use_master: bool = True,
) -> dict:
    """Route ``amount_in_sol`` Main → [Master] → Temp1..TempN → Worker."""
    wait_timeout = wait_timeout if wait_timeout is not None else _balance_check_timeout()
    results: dict = {
        "row_id": row_id,
        "status": "failed",
        "step": None,
        "error": None,
        "signatures": {},
        "temp_wallets": [],
        "amount_sent": amount_in_sol,
    }
    current_source: dict = {}
    try:
        log.separator()
        chain_desc = f"{num_temp_wallets} temp wallets, {amount_in_sol} SOL [{_speed_mode()}]"
        if not use_master:
            chain_desc += " [NO MASTER]"
        log.info(f"FORWARD CHAIN Row {row_id}", chain_desc)

        temp_wallets = []
        for _ in range(num_temp_wallets):
            priv, pub = generate_wallet()
            temp_wallets.append({"private": priv, "public": pub})
            results["temp_wallets"].append({"private": priv, "public": pub})

        await asyncio.gather(
            *[
                save_wallet_to_log(w["private"], w["public"], row_id, f"Temp{i + 1}_Forward", log_file)
                for i, w in enumerate(temp_wallets)
            ]
        )

        if use_master:
            master_address = str(Keypair.from_bytes(base58.b58decode(master_private_key)).pubkey())
            results["step"] = "Main -> Master"
            current_source = {"private": main_private_key, "public": "<main>"}
            results["signatures"]["main_to_master"] = await send_sol(
                rpc_url, main_private_key, master_address, amount_in_sol, True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())

            results["step"] = "Master -> Temp1"
            current_source = {"private": master_private_key, "public": master_address}
            results["signatures"]["master_to_temp1"] = await drain_sol_wallet(
                rpc_url, master_private_key, temp_wallets[0]["public"], True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())
        else:
            results["step"] = "Main -> Temp1"
            current_source = {"private": main_private_key, "public": "<main>"}
            results["signatures"]["main_to_temp1"] = await send_sol(
                rpc_url, main_private_key, temp_wallets[0]["public"], amount_in_sol, True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())

        for i in range(num_temp_wallets - 1):
            results["step"] = f"Temp{i + 1} -> Temp{i + 2}"
            current_source = temp_wallets[i]
            results["signatures"][f"temp{i + 1}_to_temp{i + 2}"] = await drain_sol_wallet(
                rpc_url, temp_wallets[i]["private"], temp_wallets[i + 1]["public"], True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())

        results["step"] = f"Temp{num_temp_wallets} -> Worker"
        current_source = temp_wallets[-1]
        results["signatures"][f"temp{num_temp_wallets}_to_worker"] = await drain_sol_wallet(
            rpc_url, temp_wallets[-1]["private"], worker_address, True, wait_timeout
        )

        results["status"] = "success"
        results["step"] = "completed"
        log.success("FORWARD CHAIN COMPLETED")
        log.separator()
    except Exception as exc:  # noqa: BLE001
        results["error"] = str(exc)
        log.error(f"FORWARD ERROR at {results['step']}", str(exc))
        if current_source and current_source.get("public") != "<main>":
            try:
                await save_stuck_wallet_to_error_log(
                    current_source["private"], current_source["public"], row_id,
                    results["step"] or "unknown", str(exc), log_file,
                )
            except Exception as log_err:  # noqa: BLE001
                log.warning("Failed to log stuck wallet", str(log_err))
    return results


async def reverse_transaction_chain(
    rpc_url: str,
    worker_private_key: str,
    master_private_key: str,
    main_address: str,
    row_id: Any,
    log_file: Path,
    num_temp_wallets: int = 1,
    wait_timeout: int | None = None,
    use_master: bool = True,
) -> dict:
    """Route the worker's balance Worker → Temp1..TempN → [Master] → Main."""
    wait_timeout = wait_timeout if wait_timeout is not None else _balance_check_timeout()
    results: dict = {
        "row_id": row_id,
        "status": "failed",
        "step": None,
        "error": None,
        "signatures": {},
        "temp_wallets": [],
    }
    current_source: dict = {}
    try:
        log.separator()
        chain_desc = f"{num_temp_wallets} temp wallets [{_speed_mode()}]"
        if not use_master:
            chain_desc += " [NO MASTER]"
        log.info(f"REVERSE CHAIN Row {row_id}", chain_desc)

        temp_wallets = []
        for _ in range(num_temp_wallets):
            priv, pub = generate_wallet()
            temp_wallets.append({"private": priv, "public": pub})
            results["temp_wallets"].append({"private": priv, "public": pub})

        await asyncio.gather(
            *[
                save_wallet_to_log(w["private"], w["public"], row_id, f"Temp{i + 1}_Reverse", log_file)
                for i, w in enumerate(temp_wallets)
            ]
        )

        results["step"] = "Worker -> Temp1"
        worker_pubkey = str(Keypair.from_bytes(base58.b58decode(worker_private_key)).pubkey())
        current_source = {"private": worker_private_key, "public": worker_pubkey}
        results["signatures"]["worker_to_temp1"] = await drain_sol_wallet(
            rpc_url, worker_private_key, temp_wallets[0]["public"], True, wait_timeout
        )
        await asyncio.sleep(_transaction_delay())

        for i in range(num_temp_wallets - 1):
            results["step"] = f"Temp{i + 1} -> Temp{i + 2}"
            current_source = temp_wallets[i]
            results["signatures"][f"temp{i + 1}_to_temp{i + 2}"] = await drain_sol_wallet(
                rpc_url, temp_wallets[i]["private"], temp_wallets[i + 1]["public"], True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())

        if use_master:
            master_address = str(Keypair.from_bytes(base58.b58decode(master_private_key)).pubkey())
            results["step"] = f"Temp{num_temp_wallets} -> Master"
            current_source = temp_wallets[-1]
            results["signatures"][f"temp{num_temp_wallets}_to_master"] = await drain_sol_wallet(
                rpc_url, temp_wallets[-1]["private"], master_address, True, wait_timeout
            )
            await asyncio.sleep(_transaction_delay())

            results["step"] = "Master -> Main"
            current_source = {"private": master_private_key, "public": master_address}
            results["signatures"]["master_to_main"] = await drain_sol_wallet(
                rpc_url, master_private_key, main_address, True, wait_timeout
            )
        else:
            results["step"] = f"Temp{num_temp_wallets} -> Main"
            current_source = temp_wallets[-1]
            results["signatures"][f"temp{num_temp_wallets}_to_main"] = await drain_sol_wallet(
                rpc_url, temp_wallets[-1]["private"], main_address, True, wait_timeout
            )

        results["status"] = "success"
        results["step"] = "completed"
        log.success("REVERSE CHAIN COMPLETED")
        log.separator()
    except Exception as exc:  # noqa: BLE001
        results["error"] = str(exc)
        log.error(f"REVERSE ERROR at {results['step']}", str(exc))
        if current_source:
            try:
                await save_stuck_wallet_to_error_log(
                    current_source["private"], current_source["public"], row_id,
                    results["step"] or "unknown", str(exc), log_file,
                )
            except Exception as log_err:  # noqa: BLE001
                log.warning("Failed to log stuck wallet", str(log_err))
    return results


async def process_row(
    row_id: Any,
    main_pk: str,
    master_pk: str,
    worker_pk: str,
    rpc_url: str,
    log_file: Path,
    num_temp_wallets: int,
    index: int,
    total: int,
) -> dict:
    """Run forward then reverse chain for one spreadsheet row."""
    log.separator("═")
    log.info(f"PROCESSING ROW {row_id}", f"({index + 1}/{total})")
    log.separator("═")
    try:
        worker_addr = str(Keypair.from_bytes(base58.b58decode(worker_pk)).pubkey())
        main_addr = str(Keypair.from_bytes(base58.b58decode(main_pk)).pubkey())
        log.info("Worker address", f"{worker_addr[:8]}...{worker_addr[-4:]}")
        log.info("Main address", f"{main_addr[:8]}...{main_addr[-4:]}")

        forward = await forward_transaction_chain(
            rpc_url=rpc_url, main_private_key=main_pk, master_private_key=master_pk,
            worker_address=worker_addr, row_id=row_id, log_file=log_file,
            num_temp_wallets=num_temp_wallets, wait_timeout=300,
        )
        if forward["status"] == "success":
            await asyncio.sleep(5)
            reverse = await reverse_transaction_chain(
                rpc_url=rpc_url, worker_private_key=worker_pk, master_private_key=master_pk,
                main_address=main_addr, row_id=row_id, log_file=log_file,
                num_temp_wallets=num_temp_wallets, wait_timeout=300,
            )
            return {
                "row_id": row_id,
                "forward_status": forward["status"],
                "reverse_status": reverse["status"],
                "forward_error": forward.get("error"),
                "reverse_error": reverse.get("error"),
                "forward_temp_wallets": len(forward.get("temp_wallets", [])),
                "reverse_temp_wallets": len(reverse.get("temp_wallets", [])),
            }
        log.warning("Forward chain failed", "Skipping reverse chain")
        return {
            "row_id": row_id,
            "forward_status": forward["status"],
            "reverse_status": "skipped",
            "forward_error": forward.get("error"),
            "reverse_error": None,
            "forward_temp_wallets": len(forward.get("temp_wallets", [])),
            "reverse_temp_wallets": 0,
        }
    except Exception as exc:  # noqa: BLE001
        log.error(f"Row {row_id} error", str(exc))
        return {
            "row_id": row_id,
            "forward_status": "error",
            "reverse_status": "skipped",
            "forward_error": str(exc),
            "reverse_error": None,
            "forward_temp_wallets": 0,
            "reverse_temp_wallets": 0,
        }
