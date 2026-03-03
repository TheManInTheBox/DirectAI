"""
Whisper transcription support for the TRT-LLM engine.

Provides POST /v1/audio/transcriptions — OpenAI-compatible transcription
endpoint. Uses TRT-LLM's Whisper pipeline when available, falls back to
a stub response when tensorrt_llm is not installed (dev/CI mode).

The endpoint is registered on the FastAPI app only when the engine's
configured modality is 'transcription' (TRTLLM_MODALITY=transcription).

Architecture:
  TRT-LLM Whisper is an encoder-decoder model — completely different from
  the autoregressive LLM pipeline in runner.py. The inference path is:

    audio bytes → ffmpeg decode → 16 kHz float32
    → mel spectrogram (STFT + mel filterbank)
    → encoder TRT engine → encoder hidden states
    → decoder TRT engine (beam search) → token IDs
    → tiktoken decode → text

  The engine directory must contain:
    engine_dir/encoder/rank0.engine   (compiled encoder)
    engine_dir/encoder/config.json    (encoder config)
    engine_dir/decoder/rank0.engine   (compiled decoder)
    engine_dir/decoder/config.json    (decoder config)

  Assets directory (tokenizer_dir) must contain:
    multilingual.tiktoken  (or gpt2.tiktoken for English-only models)
    mel_filters.npz        (precomputed mel filterbank from OpenAI Whisper)
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from engine.whisper_preprocessing import (
    N_SAMPLES,
    SAMPLE_RATE,
    compute_mel_spectrogram,
    decode_audio,
    pad_or_trim,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Max audio file size: 25 MB (matches OpenAI's limit)
_MAX_AUDIO_BYTES = 25 * 1024 * 1024


class WhisperRunner:
    """
    Wrapper around TRT-LLM Whisper encoder-decoder inference.

    When tensorrt_llm is not installed, operates in stub mode
    returning a placeholder transcription (for dev/CI testing).

    Production path uses TRT-LLM's ModelRunnerCpp for the C++ runtime
    with inflight batching — the recommended path per NVIDIA docs.
    """

    def __init__(self) -> None:
        self._model_runner = None  # ModelRunnerCpp instance
        self._tokenizer = None  # tiktoken Encoding
        self._n_mels: int = 128  # Overridden from engine config
        self._eot_id: int = 0  # End-of-text token ID
        self._assets_dir: str | None = None  # Path to mel_filters.npz
        self._loaded = False
        self._stub = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, engine_dir: str, tokenizer_dir: str) -> None:
        """
        Load Whisper TRT-LLM engine from compiled artifacts.

        Args:
            engine_dir: Directory containing encoder/ and decoder/ TRT engines.
            tokenizer_dir: Directory containing tiktoken files and mel_filters.npz.
        """
        try:
            import torch  # noqa: F401
            from tensorrt_llm.bindings import GptJsonConfig
            from tensorrt_llm.runtime import ModelRunnerCpp

            logger.info("Loading Whisper TRT-LLM engine from %s", engine_dir)

            engine_path = Path(engine_dir)
            assets_path = Path(tokenizer_dir)
            self._assets_dir = str(assets_path)

            # ── Read encoder config ─────────────────────────────────
            encoder_config = _read_engine_config(engine_path / "encoder")
            self._n_mels = encoder_config.get("n_mels", 128)
            num_languages = encoder_config.get("num_languages", 99)

            # ── Read decoder config ─────────────────────────────────
            decoder_json_config = GptJsonConfig.parse_file(
                str(engine_path / "decoder" / "config.json")
            )
            decoder_model_config = decoder_json_config.model_config
            assert decoder_model_config.supports_inflight_batching, (
                "Whisper decoder must be built with inflight batching support. "
                "Rebuild with: --paged_kv_cache enable --remove_input_padding enable"
            )

            # ── Load tokenizer (tiktoken) ───────────────────────────
            is_multilingual = encoder_config.get("vocab_size", 0) >= 51865
            tokenizer_name = "multilingual" if is_multilingual else "gpt2"
            self._tokenizer = _load_tiktoken(tokenizer_name, num_languages, str(assets_path))
            self._eot_id = self._tokenizer.encode(
                "<|endoftext|>",
                allowed_special=self._tokenizer.special_tokens_set,
            )[0]

            # ── Load C++ model runner (encoder-decoder) ─────────────
            runner_kwargs = {
                "engine_dir": str(engine_path),
                "is_enc_dec": True,
                "max_batch_size": 16,
                "max_input_len": 3000,
                "max_output_len": 96,
                "max_beam_width": 1,
                "kv_cache_free_gpu_memory_fraction": 0.9,
                "cross_kv_cache_fraction": 0.5,
            }
            self._model_runner = ModelRunnerCpp.from_dir(**runner_kwargs)

            self._loaded = True
            logger.info(
                "Whisper TRT-LLM engine loaded — n_mels=%d, multilingual=%s",
                self._n_mels,
                is_multilingual,
            )

        except ImportError:
            logger.warning(
                "tensorrt_llm not installed — Whisper running in stub mode. "
                "Transcription requests will return placeholder text."
            )
            self._stub = True
            self._loaded = True

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float = 0.0,
    ) -> dict:
        """
        Transcribe audio bytes to text.

        Pipeline:
          1. Decode audio bytes → 16 kHz float32 (via ffmpeg)
          2. Pad/trim to 30s → compute mel spectrogram
          3. Encode mel → encoder hidden states (TRT engine)
          4. Decode → token IDs (TRT engine, beam search)
          5. Detokenize → text

        Returns an OpenAI-compatible transcription response dict.
        """
        if not self._loaded:
            raise RuntimeError("Whisper engine not loaded")

        if self._stub:
            return {
                "text": "[stub] Transcription placeholder — TRT-LLM not installed.",
            }

        import torch

        # ── 1. Decode audio ─────────────────────────────────────────
        audio = decode_audio(audio_bytes)

        # ── 2. Mel spectrogram ──────────────────────────────────────
        audio = pad_or_trim(audio, N_SAMPLES)
        mel_filters_path = None
        if self._assets_dir:
            candidate = Path(self._assets_dir) / "mel_filters.npz"
            if candidate.exists():
                mel_filters_path = str(candidate)

        mel = compute_mel_spectrogram(
            audio,
            n_mels=self._n_mels,
            mel_filters_path=mel_filters_path,
            device="cuda",
        )
        # Shape: (n_mels, T) → (1, n_mels, T) for batch dim
        mel = mel.unsqueeze(0).half()

        # Pad to even number of frames (conv layer corner case)
        if mel.shape[2] % 2:
            mel = torch.nn.functional.pad(mel, (0, 1))

        mel_input_lengths = torch.tensor(
            [mel.shape[2]], dtype=torch.int32, device="cuda"
        )

        # ── 3. Build decoder prompt ─────────────────────────────────
        text_prefix = _build_text_prefix(language=language)
        prompt_ids = self._tokenizer.encode(
            text_prefix,
            allowed_special=self._tokenizer.special_tokens_set,
        )
        decoder_input_ids = torch.tensor([prompt_ids], dtype=torch.int32, device="cuda")

        # ── 4. Run encoder-decoder inference ────────────────────────
        # ModelRunnerCpp.generate() handles the full enc-dec pipeline:
        #   mel → encoder → cross-attention → decoder with beam search
        mel_for_runner = mel.transpose(1, 2)  # (B, T, n_mels) for C++ runtime

        outputs = self._model_runner.generate(
            batch_input_ids=decoder_input_ids,
            encoder_input_features=mel_for_runner,
            encoder_output_lengths=mel_input_lengths // 2,  # downsampling factor
            max_new_tokens=96,
            end_id=self._eot_id,
            pad_id=self._eot_id,
            num_beams=1,
            output_sequence_lengths=True,
            return_dict=True,
        )
        torch.cuda.synchronize()

        # ── 5. Decode output tokens ─────────────────────────────────
        output_ids = outputs["output_ids"].cpu().numpy().tolist()
        text = self._tokenizer.decode(output_ids[0][0]).strip()

        # Remove special tokens like <|startoftranscript|>, <|en|>, etc.
        text = re.sub(r"<\|.*?\|>", "", text).strip()

        return {"text": text}


# ── Helper functions ────────────────────────────────────────────────


def _read_engine_config(component_dir: Path) -> dict:
    """Read the TRT-LLM engine config JSON for an encoder or decoder."""
    import json

    config_path = component_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Engine config not found: {config_path}")

    with open(config_path) as f:
        raw = json.load(f)

    # Config structure varies by TRT-LLM version. The relevant fields
    # are usually under 'pretrained_config' or at the top level.
    pretrained = raw.get("pretrained_config", raw)
    return pretrained


def _load_tiktoken(
    tokenizer_name: str,
    num_languages: int,
    assets_dir: str,
):
    """
    Load the tiktoken tokenizer for Whisper.

    Whisper uses tiktoken (not HuggingFace tokenizers). The multilingual
    tokenizer is stored as multilingual.tiktoken; English-only as gpt2.tiktoken.
    """
    import tiktoken

    if tokenizer_name == "multilingual":
        encoding_path = Path(assets_dir) / "multilingual.tiktoken"
    else:
        encoding_path = Path(assets_dir) / "gpt2.tiktoken"

    if not encoding_path.exists():
        raise FileNotFoundError(
            f"Tiktoken file not found: {encoding_path}. "
            f"Download from: https://raw.githubusercontent.com/openai/whisper/main/whisper/assets/"
        )

    # Build special tokens matching OpenAI Whisper
    special_tokens = _build_whisper_special_tokens(num_languages)

    with open(encoding_path) as f:
        ranks = {
            bytes.fromhex(token): int(rank)
            for token, rank in (line.split() for line in f if line.strip())
        }

    return tiktoken.Encoding(
        name=tokenizer_name,
        explicit_n_vocab=len(ranks) + len(special_tokens),
        pat_str=r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""",
        mergeable_ranks=ranks,
        special_tokens=special_tokens,
    )


def _build_whisper_special_tokens(num_languages: int) -> dict[str, int]:
    """Build the special token dict for Whisper's tiktoken tokenizer."""
    # Base vocab size for multilingual is 50257 (GPT-2 vocab)
    # Special tokens start after that
    base = 50257

    # Language codes — first 'num_languages' language tags
    _LANGUAGES = [
        "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr",
        "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi",
        "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no",
        "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk",
        "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk",
        "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw",
        "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc",
        "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo",
        "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl",
        "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su", "yue",
    ]

    special: dict[str, int] = {}
    i = base

    special["<|endoftext|>"] = i
    i += 1
    special["<|startoftranscript|>"] = i
    i += 1

    for lang_code in _LANGUAGES[:num_languages]:
        special[f"<|{lang_code}|>"] = i
        i += 1

    special["<|translate|>"] = i
    i += 1
    special["<|transcribe|>"] = i
    i += 1
    special["<|startoflm|>"] = i
    i += 1
    special["<|startofprev|>"] = i
    i += 1
    special["<|nospeech|>"] = i
    i += 1
    special["<|notimestamps|>"] = i
    i += 1

    # Timestamp tokens (0.00 to 30.00 in 0.02s increments = 1501 tokens)
    for j in range(1501):
        special[f"<|{j * 0.02:.2f}|>"] = i
        i += 1

    return special


def _build_text_prefix(
    *,
    language: str | None = None,
    task: str = "transcribe",
) -> str:
    """Build the decoder text prefix for Whisper inference."""
    lang = language or "en"
    return f"<|startoftranscript|><|{lang}|><|{task}|><|notimestamps|>"


# Module-level runner instance — set by register_whisper_routes()
_whisper: WhisperRunner | None = None


def register_whisper_routes(app, engine_dir: str, tokenizer_dir: str) -> WhisperRunner:
    """
    Load the Whisper engine and register transcription routes on the app.

    Called from main.py lifespan when TRTLLM_MODALITY=transcription.
    """
    global _whisper
    _whisper = WhisperRunner()
    _whisper.load(engine_dir, tokenizer_dir)
    app.include_router(router)
    return _whisper


@router.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str | None = Form(default="json"),
    temperature: float | None = Form(default=None),
):
    """OpenAI-compatible audio transcription endpoint."""
    from engine.metrics import (
        WHISPER_AUDIO_DURATION,
        WHISPER_REQUEST_DURATION,
        WHISPER_REQUESTS,
    )

    if _whisper is None or not _whisper.is_loaded:
        raise HTTPException(status_code=503, detail="Whisper engine not loaded")

    # Read and validate audio file
    audio_bytes = await file.read(_MAX_AUDIO_BYTES + 1)
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds {_MAX_AUDIO_BYTES // (1024 * 1024)}MB limit.",
        )

    # Rough audio duration estimate (16-bit PCM @ 16kHz = 32 KB/s)
    estimated_audio_secs = len(audio_bytes) / (SAMPLE_RATE * 2)
    WHISPER_AUDIO_DURATION.observe(min(estimated_audio_secs, 30.0))

    try:
        t_start = time.monotonic()
        result = _whisper.transcribe(
            audio_bytes,
            language=language,
            prompt=prompt,
            temperature=temperature or 0.0,
        )
        duration = time.monotonic() - t_start

        WHISPER_REQUESTS.labels(status="ok").inc()
        WHISPER_REQUEST_DURATION.observe(duration)

        logger.info(
            "Transcription completed in %.2fs (%d bytes)",
            duration, len(audio_bytes),
        )
        return JSONResponse(content=result)

    except Exception as exc:
        WHISPER_REQUESTS.labels(status="error").inc()
        logger.exception("Transcription failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Transcription failed.",
                    "type": "server_error",
                    "code": "transcription_error",
                }
            },
        )
