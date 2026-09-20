"""The llama.cpp adapter: answers questions and holds models on disk.

Satisfies the same `Generator` protocol the previous runtime did, so
resolution, selection and the catalog do not learn that the runtime changed.

Chat is **composed, not reimplemented**. llama-server speaks OpenAI on
`/v1/chat/completions`, so the streaming, error handling and message shaping in
`OpenAICompatibleChatProvider` already work against it.

Deliberately **not** a `ModelStore`. That protocol requires `pull()`, which made
sense when the runtime fetched its own weights from a name. Here SurfSense fetches the
GGUF itself, because that is the only place `egress.require()` can hold, and
because it buys resume, checksums and the header as the file lands. Downloading
is a catalog concern; this adapter answers questions and reports what is on disk.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from modules.llm.providers.llamacpp.capabilities import Capabilities, read_capabilities
from modules.llm.providers.llamacpp.messages import for_template
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.llamacpp.thinking import THINKING_OFF
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message, Model

PROVIDER = "llamacpp"

logger = logging.getLogger(__name__)


class LlamaCppProvider:
    """One sidecar, any GGUF."""

    name = PROVIDER
    requires_key = False

    def __init__(
        self,
        base_url: str,
        models_dir: Path | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._models_dir = models_dir
        self._router = RouterClient(self._base_url, transport=transport)
        self._chat = OpenAICompatibleChatProvider(
            f"{self._base_url}/v1", transport=transport, thinking_off=THINKING_OFF
        )

    async def health(self) -> bool:
        return await self._router.health()

    async def capabilities(self, model: str) -> Capabilities:
        """What this model accepts and what its template can express.

        Read per model rather than cached across them: two files in the same
        directory can carry entirely different templates.
        """
        return read_capabilities(
            model, await self._router.raw_models(), await self._router.props(model)
        )

    async def models(self) -> list[Model]:
        """Everything in the models directory, resident or not.

        The router auto-discovers the directory, so installed state is a fact
        about disk rather than something we track separately.
        """
        return [
            Model(model.id, installed=True, capabilities=("completion",))
            for model in await self._router.models()
        ]

    async def delete(self, name: str) -> None:
        """Remove the weights from disk.

        **Not** `DELETE /models`. The router only removes what it downloaded
        into its own cache and refuses everything else: measured, `model
        name=... is not removable (not from cache)`, a 500, with the file left
        on disk. Everything SurfSense installs lands in `--models-dir`, so that
        call can never succeed for us.

        This is the same argument as install. We own the models directory; the
        runtime reads it. The router forgets the model on its next restart,
        which the preset rewrite triggers.
        """
        if self._models_dir is None:
            raise RuntimeError("no models directory configured")
        path = self._models_dir / f"{name}.gguf"
        if not path.exists():
            raise FileNotFoundError(name)
        path.unlink()

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
        json_schema: dict | None = None,
    ) -> AsyncIterator[str]:
        await self._ensure_loaded(model)
        # Downgrade at the seam: `modules/chat` assembles one conversation and
        # never learns that templates differ.
        shaped = for_template(messages, await self.capabilities(model))
        try:
            async for chunk in self._chat.chat(
                model,
                shaped,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning=reasoning,
                json_schema=json_schema,
            ):
                yield chunk
        except httpx.HTTPStatusError as error:
            # llama.cpp issue #29006: json_schema on the chat endpoint returns
            # 400 for some templates, though the model itself is fine. Losing a
            # whole Studio format to a template quirk is worse than falling back
            # to an unconstrained answer, which the parser can still repair.
            if json_schema is None or error.response.status_code != 400:
                raise
            logger.warning(
                "%s rejected a json_schema request; retrying unconstrained", model
            )
            async for chunk in self._chat.chat(
                model,
                shaped,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning=reasoning,
            ):
                yield chunk

    async def _ensure_loaded(self, model: str) -> None:
        """Models are discovered `unloaded`, so the first turn has to ask.

        Reloading a resident model would evict and re-read gigabytes between two
        turns, so this checks before it acts.
        """
        resident = {m.id for m in await self._router.models() if m.loaded}
        if model not in resident:
            await self._router.load(model)
