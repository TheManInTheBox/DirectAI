"""
Dynamic batcher for embedding requests.

Collects individual inference requests into batches and dispatches them
to the model at once for GPU efficiency. This is critical for throughput —
GPU utilization is abysmal without batching because embedding inference
is compute-bound and each text is tiny.

Design:
  - Requests are submitted via submit() and receive a Future.
  - A background loop drains the queue every `batch_timeout_ms` or when
    `max_batch_size` items are queued, whichever comes first.
  - Each batch runs a single model.embed() call.
  - Results are scattered back to individual Futures.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import numpy as np

from engine.model import EmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class _PendingRequest:
    """A single text waiting to be batched."""

    text: str
    future: asyncio.Future
    submit_time: float = field(default_factory=time.monotonic)


class DynamicBatcher:
    """
    Batches individual embedding requests for efficient GPU inference.

    Usage:
        batcher = DynamicBatcher(model, max_batch_size=256, batch_timeout_ms=5.0)
        await batcher.start()
        embedding = await batcher.submit("Hello world")  # 1-D numpy array
        await batcher.stop()
    """

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        max_batch_size: int = 256,
        batch_timeout_ms: float = 5.0,
    ) -> None:
        self._model = model
        self._max_batch_size = max_batch_size
        self._batch_timeout_s = batch_timeout_ms / 1000.0
        self._queue: asyncio.Queue[_PendingRequest] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._running = False

        # Metrics — updated by the batch loop, read by the /metrics endpoint
        self.batches_processed: int = 0
        self.items_processed: int = 0

    async def start(self) -> None:
        """Start the background batch dispatch loop."""
        self._running = True
        self._task = asyncio.create_task(self._batch_loop(), name="batcher-loop")
        logger.info(
            "Dynamic batcher started (max_batch=%d, timeout=%.1fms)",
            self._max_batch_size,
            self._batch_timeout_s * 1000,
        )

    async def stop(self) -> None:
        """Stop the batcher and drain remaining items."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Drain remaining
        await self._drain_batch()
        logger.info("Dynamic batcher stopped. Processed %d batches, %d items.", self.batches_processed, self.items_processed)

    async def submit(self, text: str) -> np.ndarray:
        """
        Submit a single text for embedding. Returns when the batch
        containing this text has been processed.

        Returns:
            1-D numpy array of shape [embedding_dim].
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._queue.put(_PendingRequest(text=text, future=future))
        return await future

    async def submit_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        Submit multiple texts. All may land in the same batch or be
        split across batches. Returns in input order.
        """
        loop = asyncio.get_running_loop()
        futures = []
        for text in texts:
            future = loop.create_future()
            await self._queue.put(_PendingRequest(text=text, future=future))
            futures.append(future)
        return await asyncio.gather(*futures)

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def is_healthy(self) -> bool:
        """True if the batcher loop is alive and accepting work."""
        return self._running and self._task is not None and not self._task.done()

    async def _batch_loop(self) -> None:
        """
        Main dispatch loop. Collects items until batch is full or timeout
        expires, then runs inference.
        """
        while self._running:
            try:
                batch = await self._collect_batch()
                if batch:
                    await self._process_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Batch loop error — continuing")

    async def _collect_batch(self) -> list[_PendingRequest]:
        """
        Wait for items. Returns up to max_batch_size items.

        Blocks until at least one item arrives, then drains greedily
        with a short timeout.
        """
        batch: list[_PendingRequest] = []

        # Block for the first item
        try:
            first = await asyncio.wait_for(
                self._queue.get(),
                timeout=0.1,  # Check _running flag periodically
            )
            batch.append(first)
        except asyncio.TimeoutError:
            return batch

        # Greedily drain up to max_batch_size with timeout
        deadline = time.monotonic() + self._batch_timeout_s
        while len(batch) < self._max_batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                batch.append(item)
            except asyncio.TimeoutError:
                break

        return batch

    async def _process_batch(self, batch: list[_PendingRequest]) -> None:
        """Run model inference on a batch and scatter results to futures."""
        texts = [req.text for req in batch]
        t0 = time.monotonic()

        try:
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(None, self._model.embed, texts)

            elapsed_ms = (time.monotonic() - t0) * 1000
            self.batches_processed += 1
            self.items_processed += len(batch)

            logger.debug(
                "Batch processed: %d items in %.1fms (%.1f items/s)",
                len(batch),
                elapsed_ms,
                len(batch) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0,
            )

            # Scatter results
            for i, req in enumerate(batch):
                if not req.future.done():
                    req.future.set_result(embeddings[i])

        except Exception as exc:
            logger.exception("Batch inference failed for %d items", len(batch))
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(exc)

    async def _drain_batch(self) -> None:
        """Process any remaining items in the queue."""
        batch = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            await self._process_batch(batch)
