"""
TRT-LLM version negotiation layer.

TensorRT-LLM's HLAPI has shifted import paths and constructor signatures
across releases. This module detects the installed version and provides
a unified interface so runner.py doesn't hardcode assumptions about any
single release.

Supported version ranges:
  - 0.12.x – 0.13.x : LLM appeared at tensorrt_llm (or tensorrt_llm.llmapi)
  - 0.14.x – 0.15.x : LLM + SamplingParams at tensorrt_llm top-level
  - 0.16.x+          : Stable HLAPI — LLM + SamplingParams at tensorrt_llm
  - Not installed     : Returns None — caller falls back to stub mode

Usage:
    from engine.compat import resolve_api, build_sampling_params

    api = resolve_api()
    if api is None:
        # stub mode
    else:
        llm = api.LLM(model=engine_dir, ...)
        sp = build_sampling_params(api, max_tokens=256, ...)
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Version ranges ──────────────────────────────────────────────────
class TRTLLMVersion(Enum):
    """Coarse version buckets that share the same API shape."""

    NOT_INSTALLED = "not_installed"
    V0_12 = "0.12"  # 0.12.x – 0.13.x
    V0_14 = "0.14"  # 0.14.x – 0.15.x
    V0_16 = "0.16"  # 0.16.x+  (current stable)


@dataclass(frozen=True)
class TRTLLMApi:
    """Resolved TRT-LLM API classes for the installed version."""

    version: TRTLLMVersion
    version_string: str
    LLM: type
    SamplingParams: type


# ── Public API ──────────────────────────────────────────────────────

def detect_version() -> TRTLLMVersion:
    """
    Detect the installed TRT-LLM version bucket.

    Returns TRTLLMVersion.NOT_INSTALLED when the package is absent.
    Raises ImportError when the package is present but too old (< 0.12).
    """
    try:
        import tensorrt_llm

        ver = getattr(tensorrt_llm, "__version__", "0.0.0")
        major, minor = _parse_version(ver)

        if major == 0 and minor < 12:
            raise ImportError(
                f"TRT-LLM {ver} is too old. Minimum supported version: 0.12.0. "
                "Upgrade with: pip install tensorrt-llm>=0.12"
            )

        if major == 0 and minor < 14:
            return TRTLLMVersion.V0_12
        if major == 0 and minor < 16:
            return TRTLLMVersion.V0_14
        # 0.16+ or any 1.x+
        return TRTLLMVersion.V0_16

    except ImportError as exc:
        # Distinguish "not installed" from "too old"
        if "too old" in str(exc):
            raise
        return TRTLLMVersion.NOT_INSTALLED


def resolve_api() -> TRTLLMApi | None:
    """
    Resolve TRT-LLM LLM + SamplingParams classes for the installed version.

    Returns None when TRT-LLM is not installed (caller uses stub mode).
    Raises ImportError when the version is unsupported or classes can't be found.
    """
    version = detect_version()

    if version == TRTLLMVersion.NOT_INSTALLED:
        logger.warning(
            "tensorrt_llm not installed — runner will operate in stub mode."
        )
        return None

    import tensorrt_llm

    ver_str = getattr(tensorrt_llm, "__version__", "unknown")
    llm_cls = _resolve_class("LLM", version)
    sp_cls = _resolve_class("SamplingParams", version)

    logger.info(
        "TRT-LLM %s detected (bucket: %s) — LLM=%s.%s, SamplingParams=%s.%s",
        ver_str,
        version.value,
        llm_cls.__module__,
        llm_cls.__name__,
        sp_cls.__module__,
        sp_cls.__name__,
    )

    return TRTLLMApi(
        version=version,
        version_string=ver_str,
        LLM=llm_cls,
        SamplingParams=sp_cls,
    )


def build_sampling_params(
    api: TRTLLMApi,
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
    end_id: int | None = None,
    pad_id: int | None = None,
) -> Any:
    """
    Construct SamplingParams with version-appropriate arguments.

    Older TRT-LLM versions (0.12–0.13) require explicit end_id / pad_id.
    Newer versions auto-detect from tokenizer and may not accept those kwargs.
    Falls back to alternate kwarg names (max_new_tokens) if needed.
    """
    base_kwargs: dict[str, Any] = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }

    # Older versions need explicit token IDs
    if api.version in (TRTLLMVersion.V0_12, TRTLLMVersion.V0_14):
        if end_id is not None:
            base_kwargs["end_id"] = end_id
        if pad_id is not None:
            base_kwargs["pad_id"] = pad_id

    try:
        return api.SamplingParams(**base_kwargs)
    except TypeError as exc:
        # Some early builds named it max_new_tokens instead of max_tokens
        if "max_tokens" in str(exc) and "max_new_tokens" not in base_kwargs:
            base_kwargs["max_new_tokens"] = base_kwargs.pop("max_tokens")
            return api.SamplingParams(**base_kwargs)
        raise


# ── Internal helpers ────────────────────────────────────────────────

# Import paths tried in priority order (newest → oldest).
_IMPORT_PATHS: dict[str, list[str]] = {
    "LLM": [
        "tensorrt_llm",           # 0.14+ top-level re-export
        "tensorrt_llm.hlapi",     # 0.14 transitional
        "tensorrt_llm.llmapi",    # 0.12–0.13
    ],
    "SamplingParams": [
        "tensorrt_llm",           # 0.14+ top-level
        "tensorrt_llm.hlapi",     # 0.14 transitional
        "tensorrt_llm.llmapi",    # 0.12–0.13
    ],
}


def _resolve_class(class_name: str, version: TRTLLMVersion) -> type:
    """Try importing *class_name* from several known module paths."""
    paths = _IMPORT_PATHS.get(class_name, [])

    for module_path in paths:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name, None)
            if cls is not None:
                return cls
        except (ImportError, AttributeError):
            continue

    raise ImportError(
        f"Cannot locate {class_name} in tensorrt_llm "
        f"(version bucket: {version.value}). "
        "The HLAPI may have been restructured — check TRT-LLM release notes."
    )


def _parse_version(version_str: str) -> tuple[int, int]:
    """
    Parse major.minor from a version string.

    Handles common suffixes: '0.16.0', '0.14.0.dev20240301', '0.12rc1'.
    """
    parts = version_str.split(".")
    try:
        major = int(parts[0]) if parts else 0
        minor_raw = parts[1] if len(parts) > 1 else "0"
        # Strip non-digit suffixes (e.g. "12dev0" → 12, "14rc1" → 14)
        minor = int("".join(c for c in minor_raw if c.isdigit()) or "0")
        return major, minor
    except (ValueError, IndexError):
        return 0, 0
