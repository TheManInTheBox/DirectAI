"""
OpenAI-compatible chat format conversion.

Converts between OpenAI ChatCompletion request/response schemas and the
raw prompt/output format that TRT-LLM expects.

Responsibilities:
  - Apply chat template (via tokenizer.apply_chat_template)
  - Build ChatCompletion response objects from raw generation output
  - Build SSE chunks for streaming responses
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from engine.runner import GenerationOutput, StreamChunk


def apply_chat_template(
    messages: list[dict[str, str]],
    tokenizer: Any,
) -> str:
    """
    Convert a list of OpenAI chat messages into a single prompt string
    using the tokenizer's built-in chat template.

    Falls back to a simple concatenation if no template is available.
    """
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        return prompt
    except Exception:
        # Fallback: simple message concatenation
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"<|{role}|>\n{content}")
        parts.append("<|assistant|>\n")
        return "\n".join(parts)


def build_completion_response(
    output: GenerationOutput,
    model_name: str,
    request_id: str | None = None,
) -> dict:
    """Build an OpenAI ChatCompletion response from generation output."""
    return {
        "id": f"chatcmpl-{request_id or uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": output.text,
                },
                "finish_reason": output.finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": output.prompt_tokens,
            "completion_tokens": output.completion_tokens,
            "total_tokens": output.prompt_tokens + output.completion_tokens,
        },
    }


def build_stream_chunk(
    chunk: StreamChunk,
    model_name: str,
    completion_id: str,
    *,
    include_role: bool = False,
) -> dict:
    """Build an OpenAI ChatCompletion chunk for SSE streaming."""
    delta: dict[str, str] = {}
    if include_role:
        delta["role"] = "assistant"
    if chunk.text:
        delta["content"] = chunk.text

    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": chunk.finish_reason,
            }
        ],
    }
