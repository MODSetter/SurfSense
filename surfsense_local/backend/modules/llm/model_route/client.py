import json
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from modules.llm.model_route.api_address import ApiNotRunningError, api_url
from modules.llm.model_route.failures import raise_from_frame
from modules.llm.model_route.schemas import ModelRef
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers.types import Delta, Message, Model
from modules.llm.resolution import ModelResolutionError, ResolvedGeneration

# How long the route may say nothing at all. It sends a keep-alive every 15
# seconds whatever it waits on, so a gap this long is a dead connection; the
# model's own start and stall budgets run inside the API.
SILENCE_SECONDS = 60.0


def resolve_routed_generation(session: Session) -> ResolvedGeneration:
    """The selected text model, reached through the API's model route.

    The selection is read here for its prompt tier and so the job keeps the
    model it started with; the API resolves, checks and admits it.
    """
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    ref = ModelRef(
        provider=selected.provider,
        name=selected.name,
        connection_id=selected.connection_id,
    )
    try:
        url = api_url()
    except ApiNotRunningError as error:
        raise ModelResolutionError(str(error)) from error
    return ResolvedGeneration(selected, RoutedGenerator(url, ref))


class RoutedGenerator:
    """`Generator.chat` over the API's model route, for a worker process.

    Failures arrive as the types a direct call raises, so a caller's handling
    does not change. Only `chat` is used by Studio; the rest answer as a
    generator that cannot tell.
    """

    name = "model_route"

    def __init__(
        self,
        api_url: str,
        model: ModelRef | None,
        *,
        priority: str = "background",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = f"{api_url.rstrip('/')}/internal/models/text/generate"
        self._model = model
        self._priority = priority
        self._transport = transport

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
        body = {
            "model": None if self._model is None else self._model.model_dump(),
            "messages": [_message(message) for message in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": reasoning,
            "json_schema": json_schema,
            "priority": self._priority,
        }
        timeout = httpx.Timeout(SILENCE_SECONDS, connect=5.0)
        async with (
            httpx.AsyncClient(timeout=timeout, transport=self._transport) as client,
            client.stream("POST", self._url, json=body) as reply,
        ):
            if reply.status_code == 409:
                raise ModelResolutionError(_detail(await reply.aread()))
            reply.raise_for_status()
            async for line in reply.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :]
                if payload == "[DONE]":
                    return
                frame = json.loads(payload)
                if frame["type"] == "text":
                    yield frame["text"]
                elif frame["type"] == "error":
                    raise_from_frame(frame)

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
        async for text in self.chat(
            model,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning=reasoning,
            json_schema=json_schema,
        ):
            yield Delta(text=text)

    async def health(self) -> bool:
        return True

    async def models(self) -> list[Model]:
        return []

    async def context_tokens(self, model: str) -> int | None:
        return None

    async def sees_images(self, model: str) -> bool | None:
        return None

    async def token_count(self, model: str, text: str) -> int | None:
        return None


def _message(message: Message) -> dict:
    import base64

    return {
        "role": message.role,
        "content": message.content,
        "images": [
            {"mime": image.mime, "data": base64.b64encode(image.data).decode()}
            for image in message.images
        ],
    }


def _detail(body: bytes) -> str:
    try:
        return str(json.loads(body).get("detail", ""))
    except ValueError:
        return body.decode(errors="replace")
