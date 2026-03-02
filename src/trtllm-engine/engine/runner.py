"""
TensorRT-LLM model runner wrapper.

Abstracts the TRT-LLM HLAPI behind a clean interface. The actual TRT-LLM
import is deferred (via engine.compat) so the rest of the codebase can be
tested without GPU hardware.

Architecture:
  - Version negotiation via engine.compat — supports 0.12+ / 0.14+ / 0.16+
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

from engine.compat import TRTLLMApi, build_sampling_params, resolve_api

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
    token_id: int | None  # Current token ID (None when no new token)
    finish_reason: str | None  # None = still generating
    completion_tokens: int  # Cumulative count of completion tokens so far


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
        self._api: TRTLLMApi | None = None  # Resolved by compat layer
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """
        Load the TRT-LLM engine and tokenizer.

        Version negotiation is handled by engine.compat — import paths
        and constructor signatures adapt to the installed TRT-LLM release.
        When TRT-LLM is not installed the runner enters stub mode.
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

        # ── TRT-LLM Runner (via compat layer) ───────────────────────
        self._api = resolve_api()

        if self._api is None:
            # tensorrt_llm not installed → stub mode
            logger.warning(
                "Running in STUB MODE — generate() returns placeholder responses. "
                "Install tensorrt_llm for real inference."
            )
            self._loaded = True
            return

        try:
            self._runner = self._api.LLM(
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
                "TRT-LLM %s engine loaded in %.1fs — tp=%d, pp=%d, max_batch=%d",
                self._api.version_string,
                load_s,
                self._tp_size,
                self._pp_size,
                self._max_batch_size,
            )
            self._loaded = True

        except Exception:
            logger.exception(
                "Failed to load TRT-LLM engine (version %s)",
                self._api.version_string,
            )
            raise

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
            sampling_params = build_sampling_params(
                self._api,
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

        Each StreamChunk carries the delta text and the *cumulative*
        completion_tokens count so the caller can report accurate usage.
        """
        if self._runner is None:
            # Stub mode — each word counts as 1 token
            token_count = 0
            for word in ["[Stub", " response", " —", " TRT-LLM", " not", " installed]"]:
                token_count += 1
                yield StreamChunk(
                    text=word,
                    token_id=0,
                    finish_reason=None,
                    completion_tokens=token_count,
                )
            token_count += 1
            yield StreamChunk(
                text="",
                token_id=0,
                finish_reason="stop",
                completion_tokens=token_count,
            )
            return

        try:
            sampling_params = build_sampling_params(
                self._api,
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
                # HLAPI yields delta text; token_ids is cumulative
                delta_text = output.outputs[0].text
                all_token_ids = output.outputs[0].token_ids
                completion_tokens = len(all_token_ids) if all_token_ids else 0
                current_token_id = all_token_ids[-1] if all_token_ids else None

                finish_reason = None
                if output.finished:
                    finish_reason = "stop"
                    if completion_tokens >= max_tokens:
                        finish_reason = "length"

                yield StreamChunk(
                    text=delta_text,
                    token_id=current_token_id,
                    finish_reason=finish_reason,
                    completion_tokens=completion_tokens,
                )

        except Exception:
            logger.exception("TRT-LLM streaming generation failed")
            yield StreamChunk(
                text="",
                token_id=None,
                finish_reason="error",
                completion_tokens=0,
            )

    @property
    def tokenizer(self):
        return self._tokenizer
