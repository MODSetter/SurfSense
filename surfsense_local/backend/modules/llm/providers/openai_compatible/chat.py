import json
from collections.abc import AsyncIterator

import httpx

from modules.llm.connections.service import parse_models
from modules.llm.profile import Fingerprint, from_remote
from modules.llm.providers.stream_deadline import with_deadlines
from modules.llm.providers.types import Message, Model

# Waiting for the first token is waiting for a model to load, which on a cold
# file is tens of seconds and on a large one more. Once tokens are flowing, a
# long gap is a fault rather than a slow machine, so the two are budgeted apart.
# The numbers live here because this is the seam that knows what it is talking
# to; a feature asking for a generation states what it wants, not how long the
# runtime may take to produce it.
FIRST_TOKEN_SECONDS = 300.0
BETWEEN_TOKENS_SECONDS = 30.0

# A backstop, not the rule. httpx's read timeout is per read, so a value below
# the load budget would quietly become the real limit and surface as a network
# error instead of saying which budget expired.
TIMEOUT = httpx.Timeout(FIRST_TOKEN_SECONDS, connect=5.0)

# Listing what an endpoint offers waits for no model, so it keeps the short
# budget: a mistyped address should fail while the person is still looking at
# the dialog.
LISTING_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
MAX_ERROR_CHARS = 400


class OpenAICompatibleChatProvider:
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        thinking_off: dict[str, object] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        # Local runtimes compose this provider and need a seam to test against.
        self._transport = transport
        # What `reasoning=False` means on this endpoint, supplied by whoever
        # knows what it is. There is no portable OpenAI shape for it, and a
        # strict endpoint rejects a field it does not recognise, so a caller
        # that cannot name one gets today's behaviour: the flag is ignored.
        self._thinking_off = thinking_off

    def _client(self, timeout: httpx.Timeout = LISTING_TIMEOUT) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        return httpx.AsyncClient(
            timeout=timeout, headers=headers, transport=self._transport
        )

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

    async def context_tokens(self, model: str) -> int | None:
        """Unknown. The `/models` listing this class speaks does not carry a
        window (that is llama.cpp's `/props`, not the OpenAI shape), so a
        caller that budgets a prompt from this must fall back to a fixed
        figure rather than assume this endpoint's real window is small."""
        return None

    async def inspect(self, name: str) -> Fingerprint:
        """What this endpoint's listing reveals about one model, for prompt tiering."""
        async with self._client() as client:
            reply = await client.get(f"{self._base_url}/models")
            reply.raise_for_status()
            payload = reply.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        return from_remote(name, rows if isinstance(rows, list) else [])

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
        if json_schema is not None:
            # Masks every token that would produce invalid JSON, so malformed
            # output stops being something to repair afterwards.
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }
        if reasoning is False and self._thinking_off is not None:
            # A caller asking for no reasoning is usually also capping tokens,
            # and a thinking model spends that cap before its first answer
            # token, so this is what keeps a short request from returning "".
            body.update(self._thinking_off)
        async for delta in with_deadlines(
            self._stream(body),
            first_item_seconds=FIRST_TOKEN_SECONDS,
            between_items_seconds=BETWEEN_TOKENS_SECONDS,
            subject="the model",
        ):
            yield delta

    async def _stream(self, body: dict[str, object]) -> AsyncIterator[str]:
        """The deltas as the endpoint sends them, with no waiting rule of its own."""
        async with (
            self._client(TIMEOUT) as client,
            client.stream(
                "POST", f"{self._base_url}/chat/completions", json=body
            ) as reply,
        ):
            if reply.status_code >= 400:
                # Same exception raise_for_status would raise, so status-based
                # handling upstream is unchanged, but carrying what the endpoint
                # actually said instead of only the status line.
                raise httpx.HTTPStatusError(
                    await _error_message(reply),
                    request=reply.request,
                    response=reply,
                )
            async for line in reply.aiter_lines():
                delta = _delta(line)
                if delta:
                    yield delta


async def _error_message(reply: httpx.Response) -> str:
    """Why the endpoint refused, which the status code alone does not say.

    A model that is not a chat model is rejected with the same 400 as a
    malformed request, and only the body tells them apart.
    """
    fallback = f"the endpoint returned HTTP {reply.status_code}"
    try:
        payload = json.loads(await reply.aread())
    except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
        return fallback
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if isinstance(message, str) and message.strip():
        return message.strip()[:MAX_ERROR_CHARS]
    return fallback


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
