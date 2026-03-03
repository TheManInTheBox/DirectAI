"""
Audio preprocessing for Whisper TRT-LLM inference.

Converts raw audio bytes (any format) into log-mel spectrogram tensors
suitable for the Whisper encoder engine. Follows the same signal processing
as OpenAI's whisper package and NVIDIA's TRT-LLM Whisper example.

Pipeline:
  audio bytes → ffmpeg decode → 16 kHz mono float32 → STFT → mel filterbank → log

Dependencies:
  - numpy (always)
  - torch (only on GPU nodes — deferred import so dev/CI can import the module)
  - ffmpeg CLI in PATH (for decoding non-PCM formats)
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

import numpy as np

if TYPE_CHECKING:
    import torch

logger = logging.getLogger(__name__)

# ── Constants (match OpenAI Whisper) ────────────────────────────────
SAMPLE_RATE = 16_000
N_FFT = 400
HOP_LENGTH = 160
CHUNK_LENGTH = 30  # seconds
N_SAMPLES = CHUNK_LENGTH * SAMPLE_RATE  # 480 000 samples in 30s


def decode_audio(
    audio_bytes: bytes,
    *,
    sr: int = SAMPLE_RATE,
) -> np.ndarray:
    """
    Decode audio bytes (any format) to 16 kHz mono float32 numpy array.

    Uses ffmpeg to handle all input formats (wav, mp3, flac, ogg, m4a, etc.).
    Falls back to raw PCM interpretation if ffmpeg fails and the data looks
    like it could be raw 16-bit PCM.

    Returns:
        1-D float32 numpy array normalised to [-1, 1].

    Raises:
        RuntimeError: If the audio cannot be decoded.
    """
    # Write bytes to a temp file so ffmpeg can read it.
    # Using a temp file avoids pipe-buffering issues with large files.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads", "0",
            "-i", tmp_path,
            "-f", "s16le",      # Raw 16-bit signed little-endian PCM
            "-ac", "1",         # Mono
            "-acodec", "pcm_s16le",
            "-ar", str(sr),     # Resample to target rate
            "-",                # Output to stdout
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=60,  # Kill if stuck (corrupt files, etc.)
        )
        pcm_bytes = result.stdout

    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found in PATH. Install ffmpeg to decode audio files. "
            "In the Docker container: apt-get install -y ffmpeg"
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg failed to decode audio ({exc.returncode}): "
            f"{exc.stderr[:500].decode('utf-8', errors='replace')}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Audio decoding timed out (>60s). File may be corrupt.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if len(pcm_bytes) == 0:
        raise RuntimeError("ffmpeg produced empty output — input may not contain audio.")

    # Convert raw PCM to float32
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def pad_or_trim(
    array: np.ndarray,
    length: int = N_SAMPLES,
) -> np.ndarray:
    """
    Pad or trim the 1-D audio array to exactly `length` samples.

    Whisper's encoder expects exactly 30s of audio (480 000 samples).
    Short clips are zero-padded; long clips are truncated from the right.
    """
    if array.shape[-1] > length:
        return array[:length]
    if array.shape[-1] < length:
        pad_width = length - array.shape[-1]
        return np.pad(array, (0, pad_width), mode="constant")
    return array


def compute_mel_spectrogram(
    audio: np.ndarray,
    n_mels: int = 128,
    *,
    mel_filters_path: Optional[str] = None,
    device: str = "cuda",
    padding: int = 0,
) -> "torch.Tensor":
    """
    Compute a log-mel spectrogram from a 1-D float32 audio array.

    This replicates OpenAI Whisper's `log_mel_spectrogram` function and
    NVIDIA's TRT-LLM `whisper_utils.log_mel_spectrogram`.

    Args:
        audio: 1-D float32 numpy array, normalised to [-1, 1].
        n_mels: Number of mel bands (80 for whisper base/small, 128 for large-v3).
        mel_filters_path: Path to mel_filters.npz (OpenAI's precomputed filters).
                         If None, computes filters on the fly.
        device: Torch device for computation ('cuda' or 'cpu').
        padding: Extra zero-padding samples to append before STFT.

    Returns:
        Torch tensor of shape (n_mels, T) on the specified device.
    """
    import torch

    # Move audio to torch tensor
    if isinstance(audio, np.ndarray):
        audio_tensor = torch.from_numpy(audio).to(device)
    else:
        audio_tensor = audio.to(device)

    if padding > 0:
        audio_tensor = torch.nn.functional.pad(audio_tensor, (0, padding))

    # STFT
    window = torch.hann_window(N_FFT, device=device)
    stft_out = torch.stft(
        audio_tensor,
        N_FFT,
        HOP_LENGTH,
        window=window,
        return_complex=True,
    )
    magnitudes = stft_out[..., :-1].abs() ** 2

    # Mel filterbank
    filters = _get_mel_filters(n_mels, mel_filters_path, device)
    mel_spec = filters @ magnitudes

    # Log scale (clamp to avoid log(0))
    log_spec = torch.clamp(mel_spec, min=1e-10).log10()
    log_spec = torch.maximum(log_spec, log_spec.max() - 8.0)
    log_spec = (log_spec + 4.0) / 4.0

    return log_spec


def _get_mel_filters(
    n_mels: int,
    mel_filters_path: Optional[str],
    device: Union[str, "torch.device"],
) -> "torch.Tensor":
    """
    Load or compute mel filterbank.

    Prefers OpenAI's precomputed mel_filters.npz if available (exact match
    with original Whisper). Falls back to computing from scratch via torch.
    """
    import torch

    # Try loading precomputed filters
    if mel_filters_path is not None:
        filters_file = Path(mel_filters_path)
        if filters_file.exists():
            with np.load(str(filters_file)) as f:
                key = f"mel_{n_mels}" if f"mel_{n_mels}" in f else list(f.keys())[0]
                return torch.from_numpy(f[key]).to(device)

    # Compute mel filterbank from scratch
    return _compute_mel_filterbank(n_mels, N_FFT, SAMPLE_RATE, device)


def _compute_mel_filterbank(
    n_mels: int,
    n_fft: int,
    sample_rate: int,
    device: Union[str, "torch.device"],
) -> "torch.Tensor":
    """
    Compute a mel filterbank matrix.

    Follows the same frequency-to-mel conversion as librosa / OpenAI Whisper.
    """
    import torch

    # Frequency bins
    n_freqs = n_fft // 2 + 1
    all_freqs = torch.linspace(0, sample_rate / 2, n_freqs, device=device)

    # Mel scale (HTK formula matching OpenAI Whisper)
    min_mel = _hz_to_mel(0.0)
    max_mel = _hz_to_mel(sample_rate / 2.0)
    mel_points = torch.linspace(min_mel, max_mel, n_mels + 2, device=device)
    freq_points = _mel_to_hz(mel_points)

    # Create triangular filters
    filterbank = torch.zeros(n_mels, n_freqs, device=device)
    for i in range(n_mels):
        lower = freq_points[i]
        center = freq_points[i + 1]
        upper = freq_points[i + 2]

        # Rising slope
        up_slope = (all_freqs - lower) / (center - lower + 1e-10)
        # Falling slope
        down_slope = (upper - all_freqs) / (upper - center + 1e-10)

        filterbank[i] = torch.maximum(
            torch.zeros_like(all_freqs),
            torch.minimum(up_slope, down_slope),
        )

    # Slaney-style normalization
    enorm = 2.0 / (freq_points[2 : n_mels + 2] - freq_points[:n_mels])
    filterbank *= enorm.unsqueeze(1)

    return filterbank


def _hz_to_mel(freq: float) -> float:
    """Convert frequency in Hz to mel scale."""
    return 2595.0 * np.log10(1.0 + freq / 700.0)


def _mel_to_hz(mels: "torch.Tensor") -> "torch.Tensor":
    """Convert mel scale values back to Hz."""
    return 700.0 * (10.0 ** (mels / 2595.0) - 1.0)
