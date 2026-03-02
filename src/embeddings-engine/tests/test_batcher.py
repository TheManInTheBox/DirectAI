"""Tests for the DynamicBatcher — batching, submit, drain."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import EMBED_DIM


def _make_mock_model() -> MagicMock:
    """Standalone mock model for batcher-only tests."""
    model = MagicMock()
    model.is_loaded = True
    model.embedding_dim = EMBED_DIM

    def fake_embed(texts: list[str]) -> np.ndarray:
        n = len(texts)
        embs = np.ones((n, EMBED_DIM), dtype=np.float32) * 0.1
        return embs

    model.embed.side_effect = fake_embed
    return model


@pytest.mark.asyncio
async def test_batcher_single_submit():
    """Submit a single text, get an embedding back."""
    from engine.batcher import DynamicBatcher

    model = _make_mock_model()
    batcher = DynamicBatcher(model, max_batch_size=4, batch_timeout_ms=50)
    await batcher.start()

    try:
        result = await batcher.submit("hello world")
        assert isinstance(result, np.ndarray)
        assert result.shape == (EMBED_DIM,)
    finally:
        await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_batch_submit():
    """Submit a batch, get ordered results."""
    from engine.batcher import DynamicBatcher

    model = _make_mock_model()
    batcher = DynamicBatcher(model, max_batch_size=8, batch_timeout_ms=50)
    await batcher.start()

    try:
        results = await batcher.submit_batch(["a", "b", "c"])
        assert len(results) == 3
        for r in results:
            assert isinstance(r, np.ndarray)
            assert r.shape == (EMBED_DIM,)
    finally:
        await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_processes_items():
    """After submitting, batches_processed and items_processed should increment."""
    from engine.batcher import DynamicBatcher

    model = _make_mock_model()
    batcher = DynamicBatcher(model, max_batch_size=4, batch_timeout_ms=50)
    await batcher.start()

    try:
        await batcher.submit_batch(["x", "y"])
        # Give the background loop a moment
        await asyncio.sleep(0.1)

        assert batcher.items_processed >= 2
        assert batcher.batches_processed >= 1
    finally:
        await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_model_error_propagates():
    """If the model raises, the awaiting future should get the exception."""
    from engine.batcher import DynamicBatcher

    model = MagicMock()
    model.embed.side_effect = RuntimeError("GPU exploded")

    batcher = DynamicBatcher(model, max_batch_size=4, batch_timeout_ms=50)
    await batcher.start()

    try:
        with pytest.raises(RuntimeError, match="GPU exploded"):
            await batcher.submit("boom")
    finally:
        await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_stop_drains():
    """stop() should process remaining queued items."""
    from engine.batcher import DynamicBatcher

    model = _make_mock_model()
    batcher = DynamicBatcher(model, max_batch_size=256, batch_timeout_ms=5000)
    await batcher.start()

    # Submit items — they might not fire before we stop (long timeout)
    futures = []
    loop = asyncio.get_running_loop()
    for text in ["a", "b", "c"]:
        f = loop.create_future()
        from engine.batcher import _PendingRequest
        import time as _time

        await batcher._queue.put(_PendingRequest(text=text, future=f, submit_time=_time.monotonic()))
        futures.append(f)

    # Stop should drain
    await batcher.stop()

    for f in futures:
        assert f.done()
        assert isinstance(f.result(), np.ndarray)
