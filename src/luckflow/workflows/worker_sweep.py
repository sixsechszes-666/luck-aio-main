"""Worker-sweep workflow: return leftover SOL from worker wallets back to Main.

Ported from ``luck_worker_sweep.py``. Checks each worker's balance and, if above
a dust threshold, runs the reverse temp-wallet chain Worker → … → Main. Uses the
generic :class:`WorkerPool` for bounded concurrency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import base58
import pandas as pd
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from luckflow.blockchain.solana import reverse_transaction_chain
from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.core.runner import WorkerPool, install_asyncio_exception_handler

SWEEP_MIN_LAMPORTS = 50_000  # ~0.00005 SOL dust threshold
LAMPORTS_PER_SOL = 1_000_000_000


def _rpc_url() -> str:
    return settings.solana.helius_rpc_url or settings.solana.rpc_url


def _wallets_log_path() -> Path:
    return settings.data_dir / "logs" / "wallets.log"


async def _get_balance_lamports(rpc_url: str, public_key: str) -> int:
    try:
        async with AsyncClient(rpc_url) as client:
            return (await client.get_balance(Pubkey.from_string(public_key), commitment=Processed)).value
    except Exception:  # noqa: BLE001
        return 0


async def _sweep_one(row: dict[str, Any], index: int, total: int) -> dict:
    rpc_url = _rpc_url()
    result = {"row_idx": index + 1, "ud_dir": row.get("UD_DIR"), "worker_pub": None,
              "balance_sol": 0.0, "status": "skipped", "error": None}

    worker_pk = row.get("PRIVATE_KEY_WORKER")
    master_pk = row.get("PRIVATE_KEY_MASTER")
    main_pk = row.get("PRIVATE_KEY_MAIN")
    if not worker_pk or not main_pk or not master_pk:
        result["status"] = "no_keys"
        return result

    try:
        worker_pub = str(Keypair.from_bytes(base58.b58decode(str(worker_pk).strip())).pubkey())
        main_address = str(Keypair.from_bytes(base58.b58decode(str(main_pk).strip())).pubkey())
        result["worker_pub"] = worker_pub

        balance_lamports = await _get_balance_lamports(rpc_url, worker_pub)
        balance_sol = balance_lamports / LAMPORTS_PER_SOL
        result["balance_sol"] = balance_sol
        short = f"{worker_pub[:8]}...{worker_pub[-4:]}"

        if balance_lamports < SWEEP_MIN_LAMPORTS:
            log.info(f"[Sweep] Row {index + 1} {short}", f"Balance {balance_sol:.9f} SOL → skip (dust)")
            result["status"] = "empty"
            return result

        log.info(f"[Sweep] Row {index + 1} {short}", f"Balance {balance_sol:.9f} SOL → reverse chain")
        reverse_result = await reverse_transaction_chain(
            rpc_url=rpc_url, worker_private_key=str(worker_pk).strip(),
            master_private_key=str(master_pk).strip(), main_address=main_address,
            row_id=index + 1, log_file=_wallets_log_path(),
            num_temp_wallets=settings.solana.num_temp_wallets, wait_timeout=settings.solana.transaction_timeout,
            use_master=settings.solana.use_master_wallet,
        )
        if reverse_result["status"] == "success":
            log.success(f"[Sweep] Row {index + 1}", f"Swept {balance_sol:.6f} SOL → Main")
            result["status"] = "swept"
        else:
            result["status"] = "failed"
            result["error"] = reverse_result.get("error", "unknown")
            log.warning(f"[Sweep] Row {index + 1} reverse chain failed", str(result["error"]))
    except Exception as exc:  # noqa: BLE001
        log.error(f"[Sweep] Row {index + 1} exception", str(exc))
        result["status"] = "error"
        result["error"] = str(exc)
    return result


async def run_worker_sweep(max_concurrent: int | None = None, excel_file: str | Path | None = None) -> list[dict]:
    """Sweep every worker wallet's leftover SOL back to its Main wallet."""
    install_asyncio_exception_handler()
    log.header("🧹 WORKER SWEEP")
    path = Path(excel_file) if excel_file else settings.excel_daily
    try:
        df = pd.read_excel(path, dtype=str).where(lambda d: d.notna(), None)
    except FileNotFoundError:
        log.error("Worker Sweep", f"File not found: {path}")
        return []
    except Exception as exc:  # noqa: BLE001
        log.error("Worker Sweep", f"Excel load error: {exc}")
        return []

    rows = [row.to_dict() for _, row in df.iterrows()]
    pool: WorkerPool[dict, dict] = WorkerPool(max_concurrent or settings.concurrency.max_onchain)
    results = await pool.run(rows, _sweep_one)
    results = [r for r in results if isinstance(r, dict)]

    swept = sum(1 for r in results if r["status"] == "swept")
    empty = sum(1 for r in results if r["status"] in ("empty", "skipped"))
    failed = sum(1 for r in results if r["status"] in ("failed", "error"))
    no_keys = sum(1 for r in results if r["status"] == "no_keys")
    log.separator("═")
    log.success("Worker Sweep complete")
    log.detail("Swept", str(swept))
    log.detail("Empty", str(empty))
    log.detail("No keys", str(no_keys))
    log.detail("Failed", str(failed))
    return results
