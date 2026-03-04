"""
ONNX Runtime inference session for embedding models.

Handles:
  - Model loading with GPU/CPU provider selection
  - Tokenization via HuggingFace tokenizers (fast Rust tokenizer)
  - Batch inference with proper attention masking
  - L2 normalization (optional)
  - Mean pooling over token embeddings
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    ONNX Runtime inference wrapper for transformer embedding models.

    Supports any model exported to ONNX with input_ids + attention_mask
    and last_hidden_state output (e.g., BGE, E5, GTE, Nomic, MiniLM).
    """

    def __init__(
        self,
        model_path: str,
        tokenizer_path: str,
        *,
        max_seq_length: int = 512,
        normalize: bool = True,
        execution_provider: str = "CUDAExecutionProvider",
        num_threads: int = 4,
    ) -> None:
        self._model_path = model_path
        self._tokenizer_path = tokenizer_path
        self._max_seq_length = max_seq_length
        self._normalize = normalize
        self._execution_provider = execution_provider
        self._num_threads = num_threads

        self._session = None
        self._tokenizer = None
        self._embedding_dim: int = 0

    def load(self) -> None:
        """Load the ONNX model and tokenizer. Call once at startup."""
        import onnxruntime as ort
        from tokenizers import Tokenizer

        # ── Tokenizer ───────────────────────────────────────────────
        tok_path = Path(self._tokenizer_path)
        if tok_path.is_file():
            self._tokenizer = Tokenizer.from_file(str(tok_path))
        else:
            # If path is a directory, look for tokenizer.json inside it
            candidate = tok_path / "tokenizer.json"
            if candidate.is_file():
                self._tokenizer = Tokenizer.from_file(str(candidate))
            else:
                raise FileNotFoundError(
                    f"Tokenizer not found at {self._tokenizer_path}. "
                    "Expected tokenizer.json file or directory containing one."
                )

        self._tokenizer.enable_truncation(max_length=self._max_seq_length)
        self._tokenizer.enable_padding(
            pad_id=0,
            pad_token="[PAD]",
            length=None,  # Dynamic padding to longest in batch
        )
        logger.info("Tokenizer loaded from %s", self._tokenizer_path)

        # ── ONNX Session ────────────────────────────────────────────
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = self._num_threads
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.log_severity_level = 3  # Warning+

        providers = self._resolve_providers()
        logger.info("Loading ONNX model from %s with providers %s", self._model_path, providers)

        t0 = time.monotonic()
        self._session = ort.InferenceSession(
            self._model_path,
            sess_options=sess_opts,
            providers=providers,
        )
        load_ms = (time.monotonic() - t0) * 1000

        # Probe embedding dimension with a dummy input
        self._embedding_dim = self._probe_embedding_dim()
        logger.info(
            "Model loaded in %.0fms — embedding_dim=%d, max_seq_length=%d, provider=%s",
            load_ms,
            self._embedding_dim,
            self._max_seq_length,
            self._session.get_providers()[0],
        )

    def _resolve_providers(self) -> list[str]:
        """Select execution providers based on configuration and availability."""
        import onnxruntime as ort

        available = set(ort.get_available_providers())

        if self._execution_provider == "CUDAExecutionProvider":
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            logger.warning("CUDA provider requested but not available. Falling back to CPU.")
            return ["CPUExecutionProvider"]

        return [self._execution_provider]

    def _get_required_input_names(self) -> set[str]:
        """Return the set of input names the ONNX model expects."""
        return {inp.name for inp in self._session.get_inputs()}

    def _build_feed(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """Build ONNX input feed, including token_type_ids if the model requires it."""
        feed: dict[str, np.ndarray] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._required_inputs:
            feed["token_type_ids"] = np.zeros_like(input_ids)
        return feed

    def _probe_embedding_dim(self) -> int:
        """Run a single dummy inference to determine output dimension."""
        self._required_inputs = self._get_required_input_names()
        encoded = self._tokenizer.encode("probe")
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        outputs = self._session.run(None, self._build_feed(input_ids, attention_mask))
        # last_hidden_state shape: [batch, seq_len, hidden_dim]
        return outputs[0].shape[-1]

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens for a given text using the loaded tokenizer."""
        encoded = self._tokenizer.encode(text)
        return len(encoded.ids)

    def embed(self, texts: list[str]) -> np.ndarray:
        """
        Compute embeddings for a batch of texts.

        Args:
            texts: List of input strings.

        Returns:
            numpy array of shape [len(texts), embedding_dim], float32.
        """
        if not self._session:
            raise RuntimeError("Model not loaded. Call load() first.")

        # ── Tokenize ────────────────────────────────────────────────
        encoded_batch = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded_batch], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded_batch], dtype=np.int64)

        # ── Inference ───────────────────────────────────────────────
        outputs = self._session.run(
            None,
            self._build_feed(input_ids, attention_mask),
        )
        # outputs[0] = last_hidden_state: [batch, seq_len, hidden_dim]
        hidden_states = outputs[0]

        # ── Mean Pooling ────────────────────────────────────────────
        # Mask padding tokens before averaging
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        sum_embeddings = (hidden_states * mask_expanded).sum(axis=1)
        sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
        embeddings = sum_embeddings / sum_mask

        # ── Normalize ───────────────────────────────────────────────
        if self._normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-12)
            embeddings = embeddings / norms

        return embeddings
