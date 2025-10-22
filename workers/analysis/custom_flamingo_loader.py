"""
Custom Audio-Flamingo Local Loader
----------------------------------

Implement load_model(local_path: str, device: str) -> tuple[object, object]
to load NVIDIA Audio-Flamingo from local weights using the official package's
inference API. Return a tuple (model, processor) where:

- model: the initialized model ready for .generate(...) or equivalent
- processor: an object with a callable interface to prepare inputs from
  (audio, text, sampling_rate) and produce tensors compatible with the model.

Example skeleton (pseudo-code):

    from nvidia_audio_flamingo import AudioFlamingo, AudioFlamingoProcessor

    def load_model(local_path: str, device: str):
        processor = AudioFlamingoProcessor.from_pretrained(local_path)
        model = AudioFlamingo.from_pretrained(local_path, device=device)
        return model, processor

Raise exceptions if loading fails; the caller will surface a clear error when
REQUIRE_FLAMINGO=true.
"""

from typing import Tuple, Any


def load_model(local_path: str, device: str) -> Tuple[Any, Any]:
    """
    Load Audio-Flamingo model and processor from a local directory using the
    NVIDIA package's API.

    Replace the body of this function with the correct calls for your package
    or internal build. Return (model, processor).
    """
    raise NotImplementedError(
        "Implement 'load_model(local_path, device)' to initialize NVIDIA Audio-Flamingo "
        "from local weights and return (model, processor)."
    )
