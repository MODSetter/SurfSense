"""The judge's endpoint: OpenRouter, so any frontier model is one flag away."""

import os

import httpx

from modules.llm.providers.types import Message

URL = "https://openrouter.ai/api/v1/chat/completions"
# One read carries the whole review, which a reasoning model can take minutes over.
TIMEOUT = httpx.Timeout(600.0, connect=10.0)


def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("set OPENROUTER_API_KEY to run the judge")
    return key


async def complete(
    model: str,
    messages: list[Message],
    key: str,
    response_format: dict | None = None,
) -> str:
    body: dict = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    if response_format is not None:
        body["response_format"] = response_format
        # Otherwise OpenRouter may route to a provider that ignores the schema.
        body["provider"] = {"require_parameters": True}
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
        response = await client.post(URL, json=body)
    if response.is_error:
        raise RuntimeError(
            f"OpenRouter answered {response.status_code}: {response.text[:400]}"
        )
    payload = response.json()
    if not payload.get("choices"):
        raise RuntimeError(f"OpenRouter sent no reply: {str(payload)[:400]}")
    return payload["choices"][0]["message"].get("content") or ""
