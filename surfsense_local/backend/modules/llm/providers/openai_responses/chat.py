from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

from modules.llm.model_type import ModelType
from modules.llm.providers.openai_compatible.chat import (
    BETWEEN_TOKENS_SECONDS,
    FIRST_TOKEN_SECONDS,
    LISTING_TIMEOUT,
    TIMEOUT,
)
from modules.llm.providers.openai_responses.errors import SignInRequiredError
from modules.llm.providers.openai_responses.events import deltas
from modules.llm.providers.openai_responses.input_items import input_items
from modules.llm.providers.openai_responses.refusal import read_refusal, refused
from modules.llm.providers.stream_deadline import with_deadlines
from modules.llm.providers.types import Delta, Message, Model

# Called with True to force a refresh, after the endpoint refused the token.
AccessToken = Callable[[bool], Awaitable[str]]


class ResponsesChatProvider:
    """A Generator over the Responses API, for a ChatGPT plan's token.

    The plan's endpoint refuses `max_output_tokens`, `reasoning`, `text.format`
    and `instructions`, so those options are accepted and dropped: a caller
    asking for JSON still parses what comes back, as for any endpoint that
    ignores a schema.
    """

    name = "openai_responses"

    def __init__(
        self,
        base_url: str,
        access_token: AccessToken,
        *,
        reads_images: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._reads_images = reads_images
        self._transport = transport

    def _client(self, token: str, timeout: httpx.Timeout) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}"},
            transport=self._transport,
        )

    async def health(self) -> bool:
        try:
            await self.models()
        except (httpx.HTTPError, SignInRequiredError, ValueError):
            return False
        return True

    async def models(self) -> list[Model]:
        """The plan's own list: entries it marks `list` are the ones to offer."""
        token = await self._access_token(False)
        async with self._client(token, LISTING_TIMEOUT) as client:
            reply = await client.get(f"{self._base_url}/models")
            reply.raise_for_status()
            payload = reply.json()
        entries = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise ValueError("the plan's model list is not a `models` array")
        return [
            Model(
                entry["slug"],
                installed=True,
                display_name=entry.get("display_name"),
                types=(ModelType.TEXT_GEN,),
            )
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("slug"), str)
            and entry.get("visibility") == "list"
        ]

    async def context_tokens(self, model: str) -> int | None:
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
        async for delta in self.chat_deltas(model, messages):
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
        body = {
            "model": model,
            "input": input_items(messages),
            "store": False,
            "stream": True,
        }
        async for delta in with_deadlines(
            self._stream(body),
            first_item_seconds=FIRST_TOKEN_SECONDS,
            between_items_seconds=BETWEEN_TOKENS_SECONDS,
            subject="the model",
        ):
            yield delta

    async def _stream(self, body: dict[str, object]) -> AsyncIterator[Delta]:
        # One refresh after a 401: the stored token can expire between reads.
        for refresh in (False, True):
            token = await self._access_token(refresh)
            async with (
                self._client(token, TIMEOUT) as client,
                client.stream(
                    "POST", f"{self._base_url}/responses", json=body
                ) as reply,
            ):
                if reply.status_code == 401 and not refresh:
                    continue
                if reply.status_code >= 400:
                    code, message = await read_refusal(reply)
                    if reply.status_code == 401:
                        raise SignInRequiredError(message)
                    raise refused(code, message, reply)
                async for delta in deltas(reply):
                    yield delta
                return
