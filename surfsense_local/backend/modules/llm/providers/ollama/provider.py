import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.providers.ollama.catalog import OFFERINGS
from modules.llm.providers.types import CatalogEntry, DownloadProgress, Message, Model

# A pull runs for minutes; a tag lookup is instant. Long read, short connect.
TIMEOUT = httpx.Timeout(600.0, connect=5.0)


class OllamaProvider:
    """Ollama over its native API: it both answers and holds models on disk."""

    name = "ollama"

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=TIMEOUT)

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                return (await client.get("/")).status_code == 200
        except httpx.HTTPError:
            return False

    async def models(self) -> list[Model]:
        async with self._client() as client:
            reply = await client.get("/api/tags")
            reply.raise_for_status()
            names = [entry["name"] for entry in reply.json().get("models", [])]
            capabilities = await asyncio.gather(
                *(self._capabilities(client, name) for name in names)
            )

        return [
            Model(name, installed=True, capabilities=caps)
            for name, caps in zip(names, capabilities, strict=True)
        ]

    def catalog(self) -> list[CatalogEntry]:
        return [
            CatalogEntry(
                name=offering.name,
                label=offering.label,
                size_gb=offering.size_gb,
            )
            for offering in OFFERINGS
        ]

    async def pull(self, name: str) -> AsyncIterator[DownloadProgress]:
        body = {"model": name, "stream": True}
        async with (
            self._client() as client,
            client.stream("POST", "/api/pull", json=body) as reply,
        ):
            reply.raise_for_status()
            async for line in reply.aiter_lines():
                if line:
                    yield _progress(json.loads(line))

    async def chat(self, model: str, messages: list[Message]) -> AsyncIterator[str]:
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        async with (
            self._client() as client,
            client.stream("POST", "/api/chat", json=body) as reply,
        ):
            reply.raise_for_status()
            async for line in reply.aiter_lines():
                if not line:
                    continue
                delta = json.loads(line).get("message", {}).get("content")
                if delta:
                    yield delta

    async def _capabilities(
        self, client: httpx.AsyncClient, name: str
    ) -> tuple[str, ...]:
        reply = await client.post("/api/show", json={"model": name})
        if reply.status_code != 200:
            return ()
        return tuple(reply.json().get("capabilities", []))


def _progress(event: dict) -> DownloadProgress:
    return DownloadProgress(
        status=event.get("status", ""),
        completed=event.get("completed", 0),
        total=event.get("total", 0),
    )
