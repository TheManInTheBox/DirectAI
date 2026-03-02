"""
TensorRT-LLM model runner wrapper.

Abstracts the TRT-LLM GenerationSession / ModelRunner behind a clean
interface. The actual TRT-LLM import is deferred so the rest of the
codebase can be tested without GPU hardware.

Architecture:
  - Loads a pre-compiled TRT-LLM engine from disk (engine_dir)
  - Loads a HuggingFace tokenizer for prompt encoding/decoding
  - Exposes generate() for non-streaming and generate_stream() for SSE
  - Handles KV cache management, TP sharding (via MPI under the hood)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class GenerationOutput:
    """Result of a single generation request."""

    text: str
    token_ids: list[int]
    finish_reason: str  # "stop", "length", "error"
    prompt_tokens: int
    completion_tokens: int


@dataclass
class StreamChunk:
    """A single token chunk emitted during streaming."""

    text: str
    token_id: int
    finish_reason: str | None  # None = still generating


class TRTLLMRunner:
    """
    Wrapper around TensorRT-LLM model runner.

    Usage:
        runner = TRTLLMRunner(engine_dir="/models/engine", tokenizer_dir="/models/tokenizer")
        runner.load()
        output = runner.generate("Hello, world!", max_tokens=100)
    """

    def __init__(
        self,
        engine_dir: str,
        tokenizer_dir: str,
        *,
        tp_size: int = 1,
        pp_size: int = 1,
        max_batch_size: int = 64,
        max_input_len: int = 4096,
        max_output_len: int = 4096,
        max_beam_width: int = 1,
        kv_cache_free_gpu_mem_fraction: float = 0.85,
        enable_chunked_context: bool = True,
    ) -> None:
        self._engine_dir = engine_dir
        self._tokenizer_dir = tokenizer_dir
        self._tp_size = tp_size
        self._pp_size = pp_size
        self._max_batch_size = max_batch_size
        self._max_input_len = max_input_len
        self._max_output_len = max_output_len
        self._max_beam_width = max_beam_width
        self._kv_cache_free_gpu_mem_fraction = kv_cache_free_gpu_mem_fraction
        self._enable_chunked_context = enable_chunked_context

        self._runner = None
        self._tokenizer = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """
        Load the TRT-LLM engine and tokenizer.

        This imports tensorrt_llm at call time — not at module level —
        so the rest of the application can be tested without TRT-LLM installed.
        """
        from transformers import AutoTokenizer

        t0 = time.monotonic()

        # ── Tokenizer ───────────────────────────────────────────────
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._tokenizer_dir,
            trust_remote_code=True,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        logger.info("Tokenizer loaded from %s", self._tokenizer_dir)

        # ── TRT-LLM Runner ──────────────────────────────────────────
        try:
            from tensorrt_llm import LLM, SamplingParams  # noqa: F401
            from tensorrt_llm.hlapi import LLM as HLAPILLM

            self._runner = HLAPILLM(
                model=self._engine_dir,
                tokenizer=self._tokenizer_dir,
                tensor_parallel_size=self._tp_size,
                pipeline_parallel_size=self._pp_size,
                kv_cache_config={
                    "free_gpu_memory_fraction": self._kv_cache_free_gpu_mem_fraction,
                    "enable_block_reuse": True,
                },
            )

            load_s = time.monotonic() - t0
            logger.info(
                "TRT-LLM engine loaded in %.1fs — tp=%d, pp=%d, max_batch=%d",
                load_s,
                self._tp_size,
                self._pp_size,
                self._max_batch_size,
            )
            self._loaded = True

        except ImportError:
            logger.warning(
                "tensorrt_llm not installed — running in STUB MODE. "
                "All generate() calls will return placeholder responses. "
                "Install tensorrt_llm for real inference."
            )
            self._loaded = True  # Mark as loaded so health checks pass

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 1.0,
        top_p: float = 1.0,
        stop: list[str] | None = None,
    ) -> GenerationOutput:
        """
        Non-streaming generation.

        Returns the complete response after all tokens are generated.
        """
        input_ids = self._tokenizer.encode(prompt)
        prompt_tokens = len(input_ids)

        if self._runner is None:
            # Stub mode
            return GenerationOutput(
                text="[TRT-LLM not installed — stub response]",
                token_ids=[],
                finish_reason="stop",
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
            )

        try:
            from tensorrt_llm import SamplingParams

            sampling_params = SamplingParams(
                max_tokens=min(max_tokens, self._max_output_len),
                temperature=temperature,
                top_p=top_p,
                end_id=self._tokenizer.eos_token_id,
                pad_id=self._tokenizer.pad_token_id,
            )

            outputs = self._runner.generate([prompt], sampling_params=[sampling_params])
            output = outputs[0]

            completion_text = output.outputs[0].text
            completion_tokens = len(output.outputs[0].token_ids)

            finish_reason = "stop"
            if completion_tokens >= max_tokens:
                finish_reason = "length"

            return GenerationOutput(
                text=completion_text,
                token_ids=list(output.outputs[0].token_ids),
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception:
            logger.exception("TRT-LLM generation failed")
            return GenerationOutput(
                text="",
                token_ids=[],
                finish_reason="error",
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
            )

    async def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> AsyncIterator[StreamChunk]:
        """
        Streaming generation — yields token chunks as they're produced.

        This uses TRT-LLM's async streaming callback to yield tokens
        without blocking the event loop.
        """
        input_ids = self._tokenizer.encode(prompt)

        if self._runner is None:
            # Stub mode
            for word in ["[Stub", " response", " —", " TRT-LLM", " not", " installed]"]:
                yield StreamChunk(text=word, token_id=0, finish_reason=None)
            yield StreamChunk(text="", token_id=0, finish_reason="stop")
            return

        try:
            from tensorrt_llm import SamplingParams

            sampling_params = SamplingParams(
                max_tokens=min(max_tokens, self._max_output_len),
                temperature=temperature,
                top_p=top_p,
                end_id=self._tokenizer.eos_token_id,
                pad_id=self._tokenizer.pad_token_id,
            )

            async for output in self._runner.generate_async(
                [prompt],
                sampling_params=[sampling_params],
                streaming=True,
            ):
                # Each output contains incrementally decoded text
                new_text = output.outputs[0].text
                token_id = output.outputs[0].token_ids[-1] if output.outputs[0].token_ids else 0

                finish_reason = None
                if output.finished:
                    finish_reason = "stop"
                    if len(output.outputs[0].token_ids) >= max_tokens:
                        finish_reason = "length"

                yield StreamChunk(
                    text=new_text,
                    token_id=token_id,
                    finish_reason=finish_reason,
                )

        except Exception:
            logger.exception("TRT-LLM streaming generation failed")
            yield StreamChunk(text="", token_id=0, finish_reason="error")

    @property
    def tokenizer(self):
        return self._tokenizer
