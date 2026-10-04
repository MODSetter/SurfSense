"""A ChatGPT plan answers through the Responses API, within what it allows.

The plan's endpoint refuses `instructions`, `reasoning`, `text.format`,
`max_output_tokens` and `tools`, so a caller's options for those are dropped
rather than sent, and a reply counts only once `response.completed` arrives.
"""

import json

import httpx
import pytest

from modules.llm.providers.openai_responses import (
    PlanLimitError,
    ResponsesChatProvider,
    SignInRequiredError,
)
from modules.llm.providers.types import Delta, Image, Message

pytestmark = pytest.mark.unit

BASE = "https://api.example/v1"
FORBIDDEN = {"instructions", "reasoning", "text", "max_output_tokens", "tools"}


def _sse(*events: dict) -> str:
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    )


def _text(*pieces: str) -> str:
    return _sse(
        *({"type": "response.output_text.delta", "delta": p} for p in pieces),
        {"type": "response.completed", "response": {"status": "completed"}},
    )


class Tokens:
    """The token getter a connection hands the generator, counting refreshes."""

    def __init__(self, *tokens: str) -> None:
        self._tokens = list(tokens)
        self.refreshes = 0

    async def __call__(self, refresh: bool) -> str:
        if refresh:
            self.refreshes += 1
            self._tokens.pop(0)
        return self._tokens[0]


def _provider(handler, tokens: Tokens | None = None) -> ResponsesChatProvider:
    return ResponsesChatProvider(
        BASE,
        tokens or Tokens("t1"),
        transport=httpx.MockTransport(handler),
    )


async def test_the_answer_streams_and_the_request_holds_only_what_the_plan_takes() -> (
    None
):
    """A system prompt goes as the developer's turn, images as input_image, nothing forbidden."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_text("Hel", "lo"))

    deltas = [
        d
        async for d in _provider(handler).chat_deltas(
            "gpt-5",
            [
                Message("system", "Be brief."),
                Message("user", "Look", images=(Image("image/png", b"png"),)),
            ],
            max_tokens=64,
            reasoning=False,
            json_schema={"type": "object"},
            temperature=0.2,
        )
    ]

    assert deltas == [Delta("Hel"), Delta("lo")]
    request = seen[0]
    body = json.loads(request.content)
    assert request.url == f"{BASE}/responses"
    assert request.headers["authorization"] == "Bearer t1"
    assert not FORBIDDEN & body.keys()
    assert (body["model"], body["store"], body["stream"]) == ("gpt-5", False, True)
    assert body["input"] == [
        {"role": "developer", "content": "Be brief."},
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Look"},
                {"type": "input_image", "image_url": "data:image/png;base64,cG5n"},
            ],
        },
    ]


async def test_an_earlier_answer_goes_back_as_the_assistants_own_text() -> None:
    """History replays as plain turns, so the model sees what it said."""
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text=_text("ok"))

    async for _ in _provider(handler).chat(
        "gpt-5",
        [
            Message("user", "hi"),
            Message("assistant", "hello"),
            Message("user", "again"),
        ],
    ):
        pass

    assert bodies[0]["input"][1] == {"role": "assistant", "content": "hello"}


async def test_an_expired_token_is_refreshed_once_and_the_request_repeated() -> None:
    """A 401 can mean only that the token aged out between reads."""
    tokens = Tokens("old", "new")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] == "Bearer old":
            return httpx.Response(401, json={"detail": "expired"})
        return httpx.Response(200, text=_text("hi"))

    reply = "".join(
        [
            c
            async for c in _provider(handler, tokens).chat(
                "gpt-5", [Message("user", "hi")]
            )
        ]
    )

    assert (reply, tokens.refreshes) == ("hi", 1)


async def test_a_token_refused_twice_means_signing_in_again() -> None:
    """A fresh token refused too is a revoked grant, not a stale one."""
    tokens = Tokens("old", "new")
    error = {
        "error": {"code": "subscription_sharing_invalid_user", "message": "revoked"}
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json=error)

    with pytest.raises(SignInRequiredError):
        async for _ in _provider(handler, tokens).chat(
            "gpt-5", [Message("user", "hi")]
        ):
            pass


async def test_a_plan_limit_before_the_stream_is_its_own_failure() -> None:
    """Not a 429 to retry: the plan's limit resets on its own schedule."""
    error = {
        "error": {
            "code": "subscription_sharing_usage_limit_exceeded",
            "message": "You have reached your limit.",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json=error)

    with pytest.raises(PlanLimitError):
        async for _ in _provider(handler).chat("gpt-5", [Message("user", "hi")]):
            pass


async def test_a_plan_limit_inside_the_stream_is_the_same_failure() -> None:
    """The limit can arrive as a failed response after a 200."""
    failed = {
        "type": "response.failed",
        "response": {
            "status": "failed",
            "error": {
                "code": "subscription_sharing_usage_limit_exceeded",
                "message": "Limit.",
            },
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_sse(failed))

    with pytest.raises(PlanLimitError):
        async for _ in _provider(handler).chat("gpt-5", [Message("user", "hi")]):
            pass


async def test_any_other_failed_response_is_an_http_error_with_its_reason() -> None:
    """httpx's own type, so chat's status classification still applies."""
    failed = {
        "type": "response.failed",
        "response": {
            "status": "failed",
            "error": {"code": "server_error", "message": "Boom."},
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_sse(failed))

    with pytest.raises(httpx.HTTPStatusError, match=r"Boom\."):
        async for _ in _provider(handler).chat("gpt-5", [Message("user", "hi")]):
            pass


async def test_a_stream_that_never_completes_is_not_an_answer() -> None:
    """OpenAI's docs: nothing counts before response.completed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=_sse({"type": "response.output_text.delta", "delta": "Hal"})
        )

    with pytest.raises(httpx.RemoteProtocolError):
        async for _ in _provider(handler).chat("gpt-5", [Message("user", "hi")]):
            pass


async def test_the_plans_listed_models_are_its_models() -> None:
    """Only entries the plan marks `list` are offered."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{BASE}/models"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "gpt-5", "display_name": "GPT-5", "visibility": "list"},
                    {"slug": "gpt-internal", "display_name": "x", "visibility": "hide"},
                ]
            },
        )

    models = await _provider(handler).models()

    assert [(m.name, m.display_name) for m in models] == [("gpt-5", "GPT-5")]
