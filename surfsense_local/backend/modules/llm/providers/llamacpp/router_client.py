"""The HTTP surface llama-server exposes in router mode.

One sidecar process holds the models directory and spawns a worker per loaded
model. The router itself costs no device memory until something loads, and it
runs happily against an empty directory, so the lifecycle is testable before any
model exists.
"""

from dataclasses import dataclass

import httpx

# A load can take minutes on a large model; a health check is instant.
TIMEOUT = httpx.Timeout(600.0, connect=5.0)


@dataclass(frozen=True)
class RouterModel:
    """One model the router discovered, and whether it is resident."""

    id: str
    loaded: bool
    args: tuple[str, ...] = ()


class RouterClient:
    """Calls the router makes available. Chat is not here: it speaks OpenAI on
    `/v1/chat/completions`, so `OpenAICompatibleChatProvider` serves it unchanged
    rather than being reimplemented."""

    def __init__(
        self, base_url: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=TIMEOUT, transport=self._transport
        )

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                return (await client.get("/health")).status_code == 200
        except httpx.HTTPError:
            return False

    async def is_router(self) -> bool:
        """Router mode, not single-model mode.

        Both answer /health, so this is the check that the sidecar came up the
        way we asked it to.
        """
        try:
            async with self._client() as client:
                reply = await client.get("/props")
                return reply.status_code == 200 and reply.json().get("role") == "router"
        except (httpx.HTTPError, ValueError):
            return False

    async def models(self) -> list[RouterModel]:
        async with self._client() as client:
            reply = await client.get("/models")
            reply.raise_for_status()
            rows = reply.json().get("data", [])
        return [
            RouterModel(
                id=row["id"],
                loaded=(row.get("status") or {}).get("value") == "loaded",
                args=tuple((row.get("status") or {}).get("args") or ()),
            )
            for row in rows
        ]

    async def raw_models(self) -> dict:
        """The `/models` payload as sent, for fields `RouterModel` does not carry."""
        async with self._client() as client:
            reply = await client.get("/models")
            reply.raise_for_status()
            return reply.json()

    async def props(self, model_id: str) -> dict:
        """One model's template capabilities and loaded settings."""
        try:
            async with self._client() as client:
                reply = await client.get("/props", params={"model": model_id})
                reply.raise_for_status()
                return reply.json()
        except (httpx.HTTPError, ValueError):
            # An older build, or a model that is not resident. Capabilities read
            # generously from an empty payload rather than failing the turn.
            return {}

    async def load(self, model_id: str) -> None:
        """Bring a model into memory.

        Deliberately sends no arguments. The router accepts an `args` field and
        ignores it, measured; per-model flags come from the preset INI instead.
        """
        async with self._client() as client:
            reply = await client.post("/models/load", json={"model": model_id})
            reply.raise_for_status()

    async def unload(self, model_id: str) -> None:
        async with self._client() as client:
            reply = await client.post("/models/unload", json={"model": model_id})
            reply.raise_for_status()

    async def delete(self, model_id: str) -> None:
        async with self._client() as client:
            reply = await client.request(
                "DELETE", "/models", params={"model": model_id}
            )
            reply.raise_for_status()
