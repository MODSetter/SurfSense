"""The llama.cpp adapter: answers questions and holds models on disk.

Satisfies the same `Generator` protocol the previous runtime did, so
resolution, selection and the catalog do not learn that the runtime changed.

Chat is **composed, not reimplemented**. llama-server speaks OpenAI on
`/v1/chat/completions`, so the streaming, error handling and message shaping in
`OpenAICompatibleChatProvider` already work against it.

Deliberately **no** load either. `--models-autoload` is on by default and the
router's proxy calls `ensure_model_ready` before forwarding, so a cold model
loads on the request that needs it. Asking as well was a check-then-act across a
socket, and it lost the race to the request already loading the model: the
router answers 400 `model is already running`, which took out title generation
on every new thread. The router owns model lifecycle; we hold no opinion about
it.

Deliberately **no** `pull()`. Fetching its own weights from a name made sense
when the runtime owned the download. Here SurfSense fetches the GGUF itself,
because that is the only place `egress.require()` can hold, and because it buys
resume, checksums and the header as the file lands. Downloading is a catalog
concern; this adapter answers questions and reports what is on disk.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import read_cached
from modules.llm.gguf.file_kind import FileKind, kind_of
from modules.llm.providers.llamacpp.capabilities import Capabilities, read_capabilities
from modules.llm.providers.llamacpp.messages import for_template
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.llamacpp.thinking import THINKING_OFF
from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.types import Delta, Message, Model

PROVIDER = "llamacpp"
# The first part of a split build is listed as a shard; it is the model.
_MODEL_KINDS = frozenset({FileKind.MODEL, FileKind.SHARD})

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
        # `/props` describes a resident model and nothing about it changes
        # between turns, so it is read once per load rather than once per
        # message. `_ensure_loaded` is the only place that clears an entry,
        # because a fresh load is the only event that can make the old answer
        # wrong (the idle timer evicted it, or a reprice changed the preset).
        self._capabilities_cache: dict[str, Capabilities] = {}
        self._chat = OpenAICompatibleChatProvider(
            f"{self._base_url}/v1", transport=transport, thinking_off=THINKING_OFF
        )

    async def health(self) -> bool:
        return await self._router.health()

    async def capabilities(self, model: str) -> Capabilities:
        """What this model accepts and what its template can express.

        Cached per model rather than fetched per message: two files in the
        same directory can carry entirely different templates, so the cache
        is keyed by model id, never assumed to hold across them. What it does
        hold across is repeated calls for the *same* resident model, since
        nothing about a loaded model's template or window changes on its own.
        Nothing invalidates it, and nothing needs to: `get_provider()` builds a
        fresh adapter per call, so the cache cannot outlive the resolution that
        created it, let alone the sidecar restart a preset rewrite triggers.
        """
        cached = self._capabilities_cache.get(model)
        if cached is not None:
            return cached
        caps = read_capabilities(
            model, await self._router.raw_models(), await self._router.props(model)
        )
        self._capabilities_cache[model] = caps
        return caps

    async def context_tokens(self, model: str) -> int | None:
        """The window this model is loaded with, from the same `/props` read
        capabilities already makes. Not the window we requested: what the
        fitter actually allocated, in case it differs."""
        return (await self.capabilities(model)).context_tokens

    async def token_count(self, model: str, text: str) -> int | None:
        """The exact cost of this text, by the router's own tokenizer.

        None on anything short of a clean count, same as `context_tokens`: a
        caller pricing history from this must fall back to an estimate rather
        than trust a failure as a token count.
        """
        try:
            return await self._router.tokenize(model, text)
        except httpx.HTTPError:
            return None

    async def models(self) -> list[Model]:
        """Every model in the models directory, resident or not, typed from its
        own header.

        The router auto-discovers the directory, so installed state is a fact
        about disk. It also lists what is not a model (a projector beside its
        weights), and a model that is not a chat model (a downloaded embedder),
        so each file's header says which it is.
        """
        models = []
        for listed in await self._router.models():
            typed = self._typed(listed.id)
            if typed is not None:
                models.append(typed)
        return models

    def _typed(self, name: str) -> Model | None:
        """None for a file that is not a model at all."""
        if self._models_dir is None:
            return Model(name, installed=True, known=False)
        header = read_cached(self._models_dir / f"{name}.gguf")
        if header is not None and kind_of(header).kind not in _MODEL_KINDS:
            return None
        architecture = (
            str(header.metadata.get("general.architecture", "")) if header else ""
        )
        found = classify(architecture, readable=header is not None)
        return Model(
            name,
            installed=True,
            capabilities=tuple(t.value for t in found.types),
            types=found.types,
            known=found.known,
        )

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
        """The answer text alone, for callers that have no use for the trace."""
        async for delta in self.chat_deltas(
            model,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning=reasoning,
            json_schema=json_schema,
        ):
            if not delta.reasoning:
                yield delta.text

    async def chat_deltas(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
        json_schema: dict | None = None,
    ) -> AsyncIterator[Delta]:
        # Downgrade at the seam: `modules/chat` assembles one conversation and
        # never learns that templates differ.
        shaped = for_template(messages, await self.capabilities(model))
        try:
            async for delta in self._chat.chat_deltas(
                model,
                shaped,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning=reasoning,
                json_schema=json_schema,
            ):
                yield delta
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
            async for delta in self._chat.chat_deltas(
                model,
                shaped,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning=reasoning,
            ):
                yield delta
