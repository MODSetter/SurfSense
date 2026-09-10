import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.connections.service import parse_models
from modules.llm.providers.types import Message, Model

TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class OpenAICompatibleChatProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _client(self) -> httpx.AsyncClient:
        headers = (
            {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        )
        return httpx.AsyncClient(timeout=TIMEOUT, headers=headers)

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                reply = await client.get(f"{self._base_url}/models")
                return reply.status_code == 200
        except httpx.HTTPError:
            return False

    async def models(self) -> list[Model]:
        async with self._client() as client:
            reply = await client.get(f"{self._base_url}/models")
            reply.raise_for_status()
            discovered = parse_models(reply.json())
        return [
            Model(
                model.name,
                installed=True,
                capabilities=model.capabilities,
            )
            for model in discovered
        ]

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
    ) -> AsyncIterator[str]:
        body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": True,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        # `reasoning` is intentionally ignored: it has no portable OpenAI shape.
        async with (
            self._client() as client,
            client.stream(
                "POST", f"{self._base_url}/chat/completions", json=body
            ) as reply,
        ):
            reply.raise_for_status()
            async for line in reply.aiter_lines():
                delta = _delta(line)
                if delta:
                    yield delta


def _delta(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    choices = json.loads(payload).get("choices")
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")
