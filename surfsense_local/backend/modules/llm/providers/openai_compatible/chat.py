import base64
import json
import logging
from collections.abc import AsyncIterator

import httpx

from modules.llm.connections.conversation_fields import conversation_fields
from modules.llm.connections.key_headers import key_headers
from modules.llm.connections.service import parse_models
from modules.llm.profile import Fingerprint, from_remote
from modules.llm.providers.prompt_reuse import chunk_reuse, log_reuse
from modules.llm.providers.stream_deadline import with_deadlines
from modules.llm.providers.types import Delta, Message, Model, PromptProgress

logger = logging.getLogger(__name__)

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
        prompt_progress: dict[str, object] | None = None,
        reads_images: bool = False,
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
        # The fields that ask an endpoint to report prompt progress, where it
        # has any; None sends nothing, since a strict endpoint rejects them.
        self._prompt_progress = prompt_progress
        # Decided by whoever resolved this endpoint, from the manifest; the
        # endpoint itself is never asked.
        self._reads_images = reads_images

    def _client(self, timeout: httpx.Timeout = LISTING_TIMEOUT) -> httpx.AsyncClient:
        headers = key_headers(self._base_url, self._api_key)
        return httpx.AsyncClient(
            timeout=timeout, headers=headers, transport=self._transport
        )

    async def sees_images(self, model: str) -> bool | None:
        return self._reads_images

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
                capabilities=model.types,
                types=model.types,
                known=model.capability_known,
            )
            for model in discovered
        ]

    async def context_tokens(self, model: str) -> int | None:
        """Unknown. The `/models` listing this class speaks does not carry a
        window (that is llama.cpp's `/props`, not the OpenAI shape), so a
        caller that budgets a prompt from this must fall back to a fixed
        figure rather than assume this endpoint's real window is small."""
        return None

    async def token_count(self, model: str, text: str) -> int | None:
        """Unknown, for the same reason as `context_tokens`: the OpenAI shape
        this class speaks has no tokenize endpoint, and every backend behind
        it uses its own encoding, so a caller here must keep its estimate."""
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
        conversation: str | None = None,
    ) -> AsyncIterator[str]:
        """The answer text alone, for callers that have no use for the trace."""
        async for delta in self.chat_deltas(
            model,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning=reasoning,
            json_schema=json_schema,
            conversation=conversation,
        ):
            if not delta.reasoning and delta.progress is None:
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
        conversation: str | None = None,
    ) -> AsyncIterator[Delta]:
        body: dict[str, object] = {
            "model": model,
            "messages": [_message(message) for message in messages],
            "stream": True,
            **conversation_fields(self._base_url, model, conversation),
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
        if self._prompt_progress is not None:
            body.update(self._prompt_progress)
        try:
            async for delta in self._deltas(body):
                yield delta
        except httpx.HTTPStatusError as error:
            # Not every endpoint takes a schema: llama.cpp refuses one for some
            # templates (issue #29006), and some hosted APIs for every model.
            # The refusal comes before any token, and losing a whole Studio
            # format to it is worse than an unconstrained answer, which the
            # parser still reads.
            if json_schema is None or error.response.status_code != 400:
                raise
            logger.warning(
                "%s refused a json_schema request; retrying unconstrained", model
            )
            del body["response_format"]
            async for delta in self._deltas(body):
                yield delta

    async def _deltas(self, body: dict[str, object]) -> AsyncIterator[Delta]:
        """The reply under the waiting rules every chat request keeps."""
        async for delta in with_deadlines(
            self._stream(body),
            first_item_seconds=FIRST_TOKEN_SECONDS,
            between_items_seconds=BETWEEN_TOKENS_SECONDS,
            subject="the model",
            # A batch of prompt can take longer than the gap allowed between
            # tokens, so progress keeps the start budget.
            started=lambda delta: delta.progress is None,
        ):
            yield delta

    async def _stream(self, body: dict[str, object]) -> AsyncIterator[Delta]:
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
            reuse = None
            async for line in reply.aiter_lines():
                delta = _delta(line)
                if delta:
                    yield delta
                elif (reported := _reuse(line)) is not None:
                    reuse = reported
            if reuse is not None:
                log_reuse(str(body["model"]), reuse)


def _message(message: Message) -> dict[str, object]:
    """String content unless the turn carries images, so every other request is
    exactly what it was before images existed."""
    if not message.images:
        return {"role": message.role, "content": message.content}
    parts: list[dict[str, object]] = [{"type": "text", "text": message.content}]
    parts += [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{image.mime};base64,"
                + base64.b64encode(image.data).decode()
            },
        }
        for image in message.images
    ]
    return {"role": message.role, "content": parts}


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


def _delta(line: str) -> Delta | None:
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    chunk = json.loads(payload)
    if progress := _prompt_progress(chunk.get("prompt_progress")):
        return Delta("", progress=progress)
    choices = chunk.get("choices")
    if not choices:
        return None
    delta = choices[0].get("delta", {})
    if content := delta.get("content"):
        return Delta(content)
    # llama.cpp and DeepSeek name the trace `reasoning_content`; vLLM, Ollama
    # and OpenRouter name it `reasoning`.
    trace = delta.get("reasoning_content") or delta.get("reasoning")
    if isinstance(trace, str) and trace:
        return Delta(trace, reasoning=True)
    return None


def _reuse(line: str) -> tuple[int, int] | None:
    """What a chunk carrying no text says about the prompt it reused, if anything."""
    payload = line[len("data:") :].strip() if line.startswith("data:") else ""
    if not payload or payload == "[DONE]":
        return None
    chunk = json.loads(payload)
    return chunk_reuse(chunk) if isinstance(chunk, dict) else None


def _prompt_progress(reported: object) -> PromptProgress | None:
    """llama.cpp counts the cached prefix as processed; the work is what lies past it."""
    if not isinstance(reported, dict):
        return None
    total, cache, processed = (
        reported.get(key) for key in ("total", "cache", "processed")
    )
    if not all(isinstance(n, int) for n in (total, cache, processed)):
        return None
    if total <= cache:
        return None
    return PromptProgress(max(processed - cache, 0), total - cache)
