import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.model_type import ModelType
from modules.llm.providers.openai_compatible.chat import (
    BETWEEN_TOKENS_SECONDS,
    FIRST_TOKEN_SECONDS,
    LISTING_TIMEOUT,
    TIMEOUT,
    OpenAICompatibleChatProvider,
)
from modules.llm.providers.openai_responses.credentials import (
    ApiKey,
    Credential,
    PlanToken,
)
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.providers.openai_responses.events import deltas
from modules.llm.providers.openai_responses.input_items import input_items
from modules.llm.providers.openai_responses.plan_limits import REFUSED_FIELDS
from modules.llm.providers.openai_responses.refusal import read_refusal, refused
from modules.llm.providers.openai_responses.retry import (
    MAX_RETRIES,
    RETRYABLE_STATUSES,
    retry_wait,
)
from modules.llm.providers.stream_deadline import with_deadlines
from modules.llm.providers.types import Delta, Message, Model


class ResponsesChatProvider:
    """A Generator over the Responses API, with an API key or a ChatGPT plan's token.

    A plan refuses a token cap and a temperature, so for a plan those options
    are accepted and dropped.
    """

    name = "openai_responses"

    def __init__(
        self,
        base_url: str,
        credential: Credential,
        *,
        reads_images: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        pause: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._credential = credential
        self._reads_images = reads_images
        self._transport = transport
        # How a retry waits; a stop cancels it like any other await.
        self._pause = pause
        # The plan's model list, read once: it carries each model's window.
        self._plan_list: list[dict] | None = None

    async def _headers(self, refresh: bool) -> dict[str, str]:
        if isinstance(self._credential, PlanToken):
            token = await self._credential.access_token(refresh)
            return {"Authorization": f"Bearer {token}"}
        return key_headers(self._base_url, self._credential.key)

    def _client(
        self, headers: dict[str, str], timeout: httpx.Timeout
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=timeout, headers=headers, transport=self._transport
        )

    async def health(self) -> bool:
        try:
            await self.models()
        except (httpx.HTTPError, SignInRequiredError, ValueError):
            return False
        return True

    async def models(self) -> list[Model]:
        if isinstance(self._credential, ApiKey):
            return await self._listed_models()
        return [
            Model(
                entry["slug"],
                installed=True,
                display_name=entry.get("display_name"),
                types=(ModelType.TEXT_GEN,),
            )
            for entry in await self._plan_entries()
        ]

    async def _listed_models(self) -> list[Model]:
        """An API key's endpoint lists its models the OpenAI way, as the compatible client reads them."""
        assert isinstance(self._credential, ApiKey)
        listing = OpenAICompatibleChatProvider(self._base_url, self._credential.key)
        return await listing.models()

    async def _plan_entries(self) -> list[dict]:
        """The plan's own list: entries it marks `list` are the ones to offer."""
        if self._plan_list is None:
            async with self._client(
                await self._headers(False), LISTING_TIMEOUT
            ) as client:
                reply = await client.get(f"{self._base_url}/models")
                reply.raise_for_status()
                payload = reply.json()
            entries = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                raise ValueError("the plan's model list is not a `models` array")
            self._plan_list = [
                entry
                for entry in entries
                if isinstance(entry, dict)
                and isinstance(entry.get("slug"), str)
                and entry.get("visibility") == "list"
            ]
        return self._plan_list

    async def context_tokens(self, model: str) -> int | None:
        """A plan states each model's window; an API key's listing states none."""
        if isinstance(self._credential, ApiKey):
            return None
        for entry in await self._plan_entries():
            window = entry.get("context_window")
            if entry["slug"] == model and isinstance(window, int) and window > 0:
                return window
        return None

    async def sees_images(self, model: str) -> bool | None:
        return self._reads_images

    async def token_count(self, model: str, text: str) -> int | None:
        return None

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
        body: dict[str, object] = {
            "model": model,
            "input": input_items(messages),
            "store": False,
            "stream": True,
        }
        if max_tokens is not None:
            body["max_output_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if json_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "response",
                    "schema": json_schema,
                }
            }
        if isinstance(self._credential, PlanToken):
            body = {k: v for k, v in body.items() if k not in REFUSED_FIELDS}
        async for delta in with_deadlines(
            self._stream(body),
            first_item_seconds=FIRST_TOKEN_SECONDS,
            between_items_seconds=BETWEEN_TOKENS_SECONDS,
            subject="the model",
        ):
            yield delta

    async def _stream(self, body: dict[str, object]) -> AsyncIterator[Delta]:
        """The reply, after at most one plan token refresh and two brief retries.

        A temporary refusal before the reply starts is waited out, as long as
        the endpoint asks and at most a minute; a used-up plan never is.
        """
        refresh = False
        retries = 0
        plan = isinstance(self._credential, PlanToken)
        while True:
            async with (
                self._client(await self._headers(refresh), TIMEOUT) as client,
                client.stream(
                    "POST", f"{self._base_url}/responses", json=body
                ) as reply,
            ):
                # One refresh after a 401: the stored token can expire between reads.
                if plan and reply.status_code == 401 and not refresh:
                    refresh = True
                    continue
                if reply.status_code >= 400:
                    code, message = await read_refusal(reply)
                    if plan and reply.status_code == 401:
                        raise SignInRequiredError(message)
                    failure = refused(code, message, reply)
                    if (
                        reply.status_code not in RETRYABLE_STATUSES
                        or isinstance(failure, PlanLimitError)
                        or retries >= MAX_RETRIES
                    ):
                        raise failure
                    wait = retry_wait(reply, retries)
                else:
                    async for delta in deltas(reply):
                        yield delta
                    return
            retries += 1
            await self._pause(wait)
