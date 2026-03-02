"""Tests for the TRT-LLM version negotiation / compat layer."""

from __future__ import annotations

import pytest

from engine.compat import TRTLLMVersion, _parse_version, detect_version


# ── Version string parsing ──────────────────────────────────────────


class TestParseVersion:
    def test_simple(self):
        assert _parse_version("0.16.0") == (0, 16)

    def test_two_part(self):
        assert _parse_version("0.14") == (0, 14)

    def test_dev_suffix(self):
        assert _parse_version("0.14.0.dev20240301") == (0, 14)

    def test_rc_suffix(self):
        assert _parse_version("0.12rc1") == (0, 12)

    def test_major_version(self):
        assert _parse_version("1.0.0") == (1, 0)

    def test_single_number(self):
        assert _parse_version("0") == (0, 0)

    def test_garbage(self):
        assert _parse_version("notaversion") == (0, 0)

    def test_empty(self):
        assert _parse_version("") == (0, 0)


# ── Version detection ───────────────────────────────────────────────


def test_detect_version_not_installed():
    """When tensorrt_llm is absent, returns NOT_INSTALLED."""
    # In our test environment, tensorrt_llm is never installed
    result = detect_version()
    assert result == TRTLLMVersion.NOT_INSTALLED


def test_detect_version_with_mock_012(monkeypatch):
    """Mock tensorrt_llm.__version__ = 0.12.0 → V0_12."""
    import types

    fake_mod = types.ModuleType("tensorrt_llm")
    fake_mod.__version__ = "0.12.0"

    monkeypatch.setitem(__import__("sys").modules, "tensorrt_llm", fake_mod)

    result = detect_version()
    assert result == TRTLLMVersion.V0_12


def test_detect_version_with_mock_014(monkeypatch):
    """Mock tensorrt_llm.__version__ = 0.14.1 → V0_14."""
    import types

    fake_mod = types.ModuleType("tensorrt_llm")
    fake_mod.__version__ = "0.14.1"

    monkeypatch.setitem(__import__("sys").modules, "tensorrt_llm", fake_mod)

    result = detect_version()
    assert result == TRTLLMVersion.V0_14


def test_detect_version_with_mock_016(monkeypatch):
    """Mock tensorrt_llm.__version__ = 0.16.0 → V0_16."""
    import types

    fake_mod = types.ModuleType("tensorrt_llm")
    fake_mod.__version__ = "0.16.0"

    monkeypatch.setitem(__import__("sys").modules, "tensorrt_llm", fake_mod)

    result = detect_version()
    assert result == TRTLLMVersion.V0_16


def test_detect_version_with_mock_100(monkeypatch):
    """Mock tensorrt_llm.__version__ = 1.0.0 → V0_16 (latest bucket)."""
    import types

    fake_mod = types.ModuleType("tensorrt_llm")
    fake_mod.__version__ = "1.0.0"

    monkeypatch.setitem(__import__("sys").modules, "tensorrt_llm", fake_mod)

    result = detect_version()
    assert result == TRTLLMVersion.V0_16


def test_detect_version_too_old_raises(monkeypatch):
    """Mock tensorrt_llm.__version__ = 0.10.0 → ImportError."""
    import types

    fake_mod = types.ModuleType("tensorrt_llm")
    fake_mod.__version__ = "0.10.0"

    monkeypatch.setitem(__import__("sys").modules, "tensorrt_llm", fake_mod)

    with pytest.raises(ImportError, match="too old"):
        detect_version()
