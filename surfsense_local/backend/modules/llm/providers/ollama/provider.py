import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.providers.ollama.catalog import OFFERINGS
from modules.llm.providers.types import CatalogEntry, DownloadProgress, Message, Model
from modules.llm.recommendations.types import (
    InstalledModel,
    InstallPlan,
    ScoredModel,
)
from shared.config import get_llm_settings

# A pull runs for minutes; a tag lookup is instant. Long read, short connect.
TIMEOUT = httpx.Timeout(600.0, connect=5.0)


class OllamaProvider:
    """Ollama over its native API: it both answers and holds models on disk."""

    name = "ollama"
    requires_key = False

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
        return [
            Model(model.model_name, installed=True, capabilities=model.capabilities)
            for model in await self.installed_models()
        ]

    async def installed_models(self) -> list[InstalledModel]:
        async with self._client() as client:
            reply = await client.get("/api/tags")
            reply.raise_for_status()
            names = [entry["name"] for entry in reply.json().get("models", [])]
            details = await asyncio.gather(
                *(self._details(client, name) for name in names)
            )

        return [
            InstalledModel(
                runtime=self.name,
                model_name=name,
                capabilities=caps,
                quantization=quantization,
            )
            for name, (caps, quantization) in zip(names, details, strict=True)
        ]

    async def resolve(self, model: ScoredModel) -> InstallPlan | None:
        if not model.ollama_name:
            return None
        expected_bytes = (
            round(model.disk_size_gb * 1_000_000_000)
            if model.disk_size_gb is not None
            else None
        )
        quantization = model.ollama_quantization or (
            model.best_quant
            if model.best_quant
            and model.best_quant.lower() in model.ollama_name.lower()
            else None
        )
        return InstallPlan(
            canonical_id=model.canonical_id,
            runtime=self.name,
            model_name=model.ollama_name,
            expected_bytes=expected_bytes,
            quantization=quantization,
        )

    def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]:
        if plan.runtime != self.name:
            raise ValueError(f"install plan belongs to {plan.runtime}, not {self.name}")
        return self.pull(plan.model_name)

    async def cleanup_cancelled_download(self) -> None:
        models_dir = get_llm_settings().ollama_models_dir
        if models_dir is None:
            return

        blobs_dir = models_dir / "blobs"
        patterns = ("*-partial", "*-partial-*", "*.tmp")
        referenced: set[str] | None = set()
        try:
            for path in (models_dir / "manifests").rglob("*"):
                if not path.is_file():
                    continue
                manifest = json.loads(path.read_text())
                entries = [manifest["config"], *manifest.get("layers", [])]
                referenced.update(
                    entry["digest"].replace(":", "-", 1) for entry in entries
                )
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            # A bad manifest must not risk deleting a layer an installed model uses.
            referenced = None

        def cancelled_files():
            files = {path for pattern in patterns for path in blobs_dir.glob(pattern)}
            if referenced is not None:
                files.update(
                    path
                    for path in blobs_dir.glob("sha256-*")
                    if path.name not in referenced
                )
            return files

        # Ollama closes its writers asynchronously after the pull disconnects.
        # Retry briefly for Windows, where an open file cannot be unlinked.
        for attempt in range(5):
            pending = cancelled_files()
            if not pending:
                return
            for path in pending:
                with contextlib.suppress(PermissionError):
                    path.unlink(missing_ok=True)
            if attempt < 4:
                await asyncio.sleep(0.1 * (attempt + 1))

        remaining = cancelled_files()
        if remaining:
            raise OSError("Ollama still has cancelled download files open")

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

    async def delete(self, name: str) -> None:
        async with self._client() as client:
            reply = await client.request("DELETE", "/api/delete", json={"model": name})
            reply.raise_for_status()

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
    ) -> AsyncIterator[str]:
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if reasoning is not None:
            body["think"] = reasoning
        options = {
            key: value
            for key, value in (
                ("num_predict", max_tokens),
                ("temperature", temperature),
            )
            if value is not None
        }
        if options:
            body["options"] = options
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
        capabilities, _ = await self._details(client, name)
        return capabilities

    async def _details(
        self, client: httpx.AsyncClient, name: str
    ) -> tuple[tuple[str, ...], str | None]:
        reply = await client.post("/api/show", json={"model": name})
        if reply.status_code != 200:
            return (), None
        body = reply.json()
        details = body.get("details", {})
        quantization = (
            details.get("quantization_level") if isinstance(details, dict) else None
        )
        return tuple(body.get("capabilities", [])), quantization


def _progress(event: dict) -> DownloadProgress:
    return DownloadProgress(
        status=event.get("status", ""),
        completed=event.get("completed", 0),
        total=event.get("total", 0),
    )
