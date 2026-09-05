import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.providers.types import Message, Model

# Generation streams for a while; auth and model listing are quick.
TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class OpenRouterProvider:
    """OpenRouter over its OpenAI-compatible API: a hosted generator, BYO key.

    Holds no models on disk, so it is a Generator but not a ModelStore — the
    download UI stays hidden. The key is set on the instance by the registry
    from the database; without one it reports unhealthy and lists nothing.
    """

    name = "openrouter"
    requires_key = True

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _client(self) -> httpx.AsyncClient:
        headers = {"X-Title": "SurfSense"}  # OpenRouter attribution, optional
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=TIMEOUT, headers=headers
        )

    async def health(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with self._client() as client:
                return (await client.get("/key")).status_code == 200
        except httpx.HTTPError:
            return False

    async def models(self) -> list[Model]:
        if not self.api_key:
            return []
        async with self._client() as client:
            reply = await client.get("/models")
            reply.raise_for_status()
            entries = reply.json().get("data", [])

        return [
            Model(entry["id"], installed=True, capabilities=("completion",))
            for entry in entries
            if _answers_text(entry)
        ]

    async def chat(self, model: str, messages: list[Message]) -> AsyncIterator[str]:
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        async with (
            self._client() as client,
            client.stream("POST", "/chat/completions", json=body) as reply,
        ):
            reply.raise_for_status()
            async for line in reply.aiter_lines():
                delta = _delta(line)
                if delta:
                    yield delta


def _answers_text(entry: dict) -> bool:
    """Keep text-out (chat) models; skip image- or embedding-only endpoints."""
    modalities = entry.get("architecture", {}).get("output_modalities")
    return "text" in modalities if modalities else True


def _delta(line: str) -> str | None:
    """One token from an OpenAI SSE line; None for keep-alives and `[DONE]`."""
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    choices = json.loads(payload).get("choices")
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")
