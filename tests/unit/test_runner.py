"""Unit tests for the WorkerPool orchestrator."""

from __future__ import annotations

import asyncio

from luckflow.core.runner import WorkerPool


async def test_worker_pool_preserves_order_and_isolates_errors():
    async def handler(item, index, total):
        await asyncio.sleep(0)
        if item == 3:
            raise ValueError("boom")
        return item * 10

    results = await WorkerPool(2).run([1, 2, 3, 4, 5], handler)

    assert results[0] == 10
    assert results[3] == 40
    assert results[4] == 50
    assert isinstance(results[2], ValueError)  # error isolated, not raised


async def test_worker_pool_checkpoints():
    saved: list[int] = []

    async def handler(item, index, total):
        return item

    pool = WorkerPool(3, checkpoint=lambda r: saved.append(len(r)), checkpoint_every=2)
    await pool.run([1, 2, 3, 4], handler)
    assert saved  # checkpoint fired at least once


async def test_worker_pool_empty():
    async def handler(item, index, total):
        return item

    assert await WorkerPool(2).run([], handler) == []


async def test_worker_pool_respects_concurrency():
    active = 0
    peak = 0

    async def handler(item, index, total):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return item

    await WorkerPool(2).run(list(range(6)), handler)
    assert peak <= 2
