"""Generic bounded-concurrency worker pool.

The legacy ``luck_main.py`` re-implemented the same orchestration boilerplate in
**eight** different functions::

    semaphore = asyncio.Semaphore(n)
    tasks = [handler(row, i, semaphore, stats, total) for i, row in enumerate(rows)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

:class:`WorkerPool` captures that pattern exactly once. A workflow just provides
an ``async`` per-item handler; the pool owns the semaphore, scheduling, exception
isolation, progress reporting and periodic checkpointing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Generic, TypeVar

from luckflow.core import logging as log

ItemT = TypeVar("ItemT")
ResultT = TypeVar("ResultT")


def install_asyncio_exception_handler() -> None:
    """Silence noisy, harmless transport teardown errors on the running loop.

    Playwright/CDP teardown can raise "unclosed transport" / "I/O operation on
    closed pipe" on Windows. These are cosmetic; everything else is delegated to
    the default handler.
    """

    def handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        message = str(context.get("message", ""))
        exception = str(context.get("exception", ""))
        if "unclosed transport" in message or "I/O operation on closed pipe" in exception:
            return
        loop.default_exception_handler(context)

    try:
        asyncio.get_event_loop().set_exception_handler(handler)
    except RuntimeError:
        pass

# A handler receives (item, index, total) and returns a result.
Handler = Callable[[ItemT, int, int], Awaitable[ResultT]]
# Optional checkpoint callback invoked with all results gathered so far.
Checkpoint = Callable[[list[ResultT]], None]


class WorkerPool(Generic[ItemT, ResultT]):
    """Run an async handler over many items with bounded concurrency."""

    def __init__(
        self,
        concurrency: int,
        *,
        checkpoint: Checkpoint | None = None,
        checkpoint_every: int = 5,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.concurrency = concurrency
        self._checkpoint = checkpoint
        self._checkpoint_every = max(1, checkpoint_every)

    async def run(self, items: Sequence[ItemT], handler: Handler) -> list[ResultT]:
        """Process ``items`` concurrently and return results in input order.

        Exceptions raised by the handler are isolated per item: they are logged
        and surfaced as the result value (matching ``gather(return_exceptions=True)``),
        so one bad account never aborts the whole batch.
        """
        total = len(items)
        if total == 0:
            log.warning("No items to process")
            return []

        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[ResultT] = []
        results_lock = asyncio.Lock()

        async def _guarded(item: ItemT, index: int) -> ResultT:
            async with semaphore:
                try:
                    result = await handler(item, index, total)
                except Exception as exc:  # noqa: BLE001 - isolate per item
                    log.error(f"Worker {index + 1}/{total} crashed", str(exc)[:120])
                    result = exc  # type: ignore[assignment]
                async with results_lock:
                    results.append(result)
                    if self._checkpoint and len(results) % self._checkpoint_every == 0:
                        self._checkpoint(results)
                return result

        log.info("🚀 Starting worker pool", f"{total} items, concurrency={self.concurrency}")
        ordered = await asyncio.gather(
            *(_guarded(item, i) for i, item in enumerate(items))
        )

        if self._checkpoint:
            self._checkpoint(list(ordered))
        return list(ordered)
