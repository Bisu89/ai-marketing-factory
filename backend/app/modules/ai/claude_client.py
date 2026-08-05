"""Shared Claude call helper for every app/modules/ai/* generator (story,
hook, caption). Centralizes client construction, the structured-output
call, and latency timing so each sub-feature's service.py only owns its
own prompt/schema/persistence logic, not a second copy of this.
"""

import time
from dataclasses import dataclass

import anthropic

MODEL = "claude-sonnet-5"


@dataclass
class ClaudeCallResult:
    response: anthropic.types.Message
    latency_ms: int


def call_structured(
    api_key: str,
    *,
    system: str,
    user_message: str,
    output_schema: dict,
    max_tokens: int,
    model: str = MODEL,
) -> ClaudeCallResult:
    client = anthropic.Anthropic(api_key=api_key)
    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
        output_config={"format": output_schema},
    )
    latency_ms = int((time.monotonic() - start) * 1000)
    return ClaudeCallResult(response=response, latency_ms=latency_ms)
