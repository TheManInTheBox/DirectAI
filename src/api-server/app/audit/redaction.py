"""
PII redaction for audit records (Issue #65 — Redacted Logging Mode).

When ``AuditConfig.redact_pii`` is True, sensitive fields in audit blob
records are scrubbed before upload.  PostgreSQL records already exclude
full request/response bodies, so PG writes are unaffected.

Redaction targets:
  - ``ip_address``      → replaced with "[REDACTED]"
  - ``user_agent``      → replaced with "[REDACTED]"
  - ``api_key_prefix``  → replaced with "[REDACTED]"
  - ``request_body``    → message content scrubbed; structure preserved
  - ``response_body``   → replaced with "[REDACTED]"

The goal is compliance-friendly: audit *structure* (who, when, what model,
how many tokens, latency) is preserved for forensics, but no PII or
prompt/completion content survives.
"""

from __future__ import annotations

import copy
import re
from typing import Any

_REDACTED = "[REDACTED]"

# Patterns that look like PII in freeform text
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_text(text: str) -> str:
    """Replace common PII patterns in a freeform string."""
    text = _EMAIL_RE.sub(_REDACTED, text)
    text = _PHONE_RE.sub(_REDACTED, text)
    text = _SSN_RE.sub(_REDACTED, text)
    return text


def redact_message_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scrub ``content`` from a list of OpenAI-style chat messages.

    Preserves the message structure (role, tool_calls metadata, function
    name) but replaces the actual content string with ``[REDACTED]``.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        cleaned = dict(msg)
        if "content" in cleaned and cleaned["content"] is not None:
            if isinstance(cleaned["content"], str):
                cleaned["content"] = _REDACTED
            elif isinstance(cleaned["content"], list):
                # Multi-part content (vision / audio): redact text parts
                parts = []
                for part in cleaned["content"]:
                    p = dict(part)
                    if p.get("type") == "text":
                        p["text"] = _REDACTED
                    elif p.get("type") == "image_url":
                        p["image_url"] = {"url": _REDACTED}
                    parts.append(p)
                cleaned["content"] = parts
        out.append(cleaned)
    return out


def redact_blob_dict(blob_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply PII redaction to an audit blob dict.

    This operates on the output of ``AuditRecord.to_blob_dict()`` —
    it is NOT an in-place mutation; a deep copy is returned.
    """
    d = copy.deepcopy(blob_dict)

    # Direct PII fields
    d["ip_address"] = _REDACTED
    d["user_agent"] = _REDACTED
    d["api_key_prefix"] = _REDACTED

    # Request body — scrub message content but keep structure
    req_body = d.get("request_body")
    if isinstance(req_body, dict):
        if "messages" in req_body and isinstance(req_body["messages"], list):
            req_body["messages"] = redact_message_content(req_body["messages"])
        # Embeddings input
        if "input" in req_body:
            if isinstance(req_body["input"], str):
                req_body["input"] = _REDACTED
            elif isinstance(req_body["input"], list):
                req_body["input"] = [_REDACTED for _ in req_body["input"]]

    # Response body — full replacement (could be huge)
    if d.get("response_body") is not None:
        d["response_body"] = _REDACTED

    return d
