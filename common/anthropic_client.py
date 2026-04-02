"""
Anthropic API client wrappers for all four frameworks.

Provides synchronous and asynchronous versions of:
  - Standard inference (Endpoint 1: /api/inference)
  - Streaming inference (Endpoint 2: /api/inference/stream)

Sync clients (Anthropic) → Flask, Django
Async clients (AsyncAnthropic) → FastAPI, Tornado

When USE_SIMULATED is True, calls are redirected to the local
simulated endpoint instead of the real Anthropic API.
"""

import json

import httpx
from anthropic import Anthropic, AsyncAnthropic

from common.config import (
    ANTHROPIC_MODEL,
    MAX_TOKENS,
    SIMULATED_ENDPOINT_URL,
    SYSTEM_PROMPT,
    TEMPERATURE,
    USE_SIMULATED,
)

# ---------------------------------------------------------------------------
# Client singletons — created once, reused across requests
# ---------------------------------------------------------------------------
_sync_client = None
_async_client = None


def get_sync_client():
    """Return the singleton synchronous Anthropic client."""
    global _sync_client
    if _sync_client is None:
        _sync_client = Anthropic()
    return _sync_client


def get_async_client():
    """Return the singleton asynchronous Anthropic client."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncAnthropic()
    return _async_client


# ---------------------------------------------------------------------------
# REAL API — Synchronous (Flask, Django)
# ---------------------------------------------------------------------------

def inference_sync(user_message):
    """Standard inference: send prompt, receive complete response.

    Returns dict with 'response' text and 'usage' metadata.
    """
    if USE_SIMULATED:
        return _simulated_inference_sync(user_message)

    client = get_sync_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return {
        "response": message.content[0].text,
        "model": message.model,
        "usage": {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        },
    }


def stream_sync(user_message):
    """Streaming inference: yield tokens one at a time.

    Yields individual text chunks as they arrive from the API.
    Used by Flask (generator + yield) and Django (StreamingHttpResponse).
    """
    if USE_SIMULATED:
        yield from _simulated_stream_sync(user_message)
        return

    client = get_sync_client()
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# REAL API — Asynchronous (FastAPI, Tornado)
# ---------------------------------------------------------------------------

async def inference_async(user_message):
    """Async standard inference: send prompt, receive complete response.

    Returns dict with 'response' text and 'usage' metadata.
    """
    if USE_SIMULATED:
        return await _simulated_inference_async(user_message)

    client = get_async_client()
    message = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return {
        "response": message.content[0].text,
        "model": message.model,
        "usage": {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        },
    }


async def stream_async(user_message):
    """Async streaming inference: yield tokens one at a time.

    Yields individual text chunks as they arrive from the API.
    Used by FastAPI (StreamingResponse) and Tornado (self.write + self.flush).
    """
    if USE_SIMULATED:
        async for chunk in _simulated_stream_async(user_message):
            yield chunk
        return

    client = get_async_client()
    async with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# SIMULATED ENDPOINT — Synchronous
# ---------------------------------------------------------------------------

def _simulated_inference_sync(user_message):
    """Call the local simulated inference endpoint (sync)."""
    response = httpx.post(
        f"{SIMULATED_ENDPOINT_URL}/simulate/inference",
        json={"prompt": user_message},
        timeout=60.0,
    )
    return response.json()


def _simulated_stream_sync(user_message):
    """Stream from the local simulated endpoint (sync)."""
    with httpx.stream(
        "POST",
        f"{SIMULATED_ENDPOINT_URL}/simulate/stream",
        json={"prompt": user_message},
        timeout=60.0,
    ) as response:
        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                event, buffer = buffer.split("\n\n", 1)
                if event.startswith("data: "):
                    data = event[6:]
                    if data == "[DONE]":
                        return
                    yield data


# ---------------------------------------------------------------------------
# SIMULATED ENDPOINT — Asynchronous
# ---------------------------------------------------------------------------

async def _simulated_inference_async(user_message):
    """Call the local simulated inference endpoint (async)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SIMULATED_ENDPOINT_URL}/simulate/inference",
            json={"prompt": user_message},
            timeout=60.0,
        )
        return response.json()


async def _simulated_stream_async(user_message):
    """Stream from the local simulated endpoint (async)."""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{SIMULATED_ENDPOINT_URL}/simulate/stream",
            json={"prompt": user_message},
            timeout=60.0,
        ) as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)
                    if event.startswith("data: "):
                        data = event[6:]
                        if data == "[DONE]":
                            return
                        yield data