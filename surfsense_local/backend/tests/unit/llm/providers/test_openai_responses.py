"""A model answers through the Responses API, with an API key or a ChatGPT plan's token.

A plan refuses `max_output_tokens` and `temperature`, so a caller's options for
those are dropped for a plan only, and a reply counts only once
`response.completed` arrives.
"""

import json

import httpx
import pytest

from modules.llm.providers.openai_responses import (
    ApiKey,
    PlanLimitError,
    PlanToken,
    ResponsesChatProvider,
    SignInRequiredError,
)
from modules.llm.providers.types import Delta, Image, Message

pytestmark = pytest.mark.unit

BASE = "https://api.example/v1"
PLAN_REFUSES = {"max_output_tokens", "temperature"}


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
        PlanToken(tokens or Tokens("t1")),
        transport=httpx.MockTransport(handler),
    )


async def test_a_plans_request_drops_the_cap_and_temperature_and_keeps_the_schema() -> (
    None
):
    """A system prompt goes as the developer's turn, images as input_image, a schema as text.format."""
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
    assert not PLAN_REFUSES & body.keys()
    assert (body["model"], body["store"], body["stream"]) == ("gpt-5", False, True)
    assert body["text"] == {
        "format": {
            "type": "json_schema",
            "name": "response",
            "schema": {"type": "object"},
        }
    }
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


async def test_a_conversation_goes_with_its_cache_key() -> None:
    """Requests sharing a key are routed to the machine likeliest to hold their
    prompt. The plan's endpoint rejects `prompt_cache_retention`, not the key."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_text("Hi"))

    async for _ in _provider(handler).chat_deltas(
        "gpt-5", [Message("user", "hi")], conversation="thread-7"
    ):
        pass

    assert json.loads(seen[0].content)["prompt_cache_key"] == "thread-7"


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


async def test_an_api_keys_request_carries_the_cap_and_temperature() -> None:
    """Only a plan refuses them; a key's endpoint takes the whole request."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_text("ok"))

    provider = ResponsesChatProvider(
        BASE, ApiKey("sk-1"), transport=httpx.MockTransport(handler)
    )
    async for _ in provider.chat(
        "fugu", [Message("user", "hi")], max_tokens=64, temperature=0.2
    ):
        pass

    body = json.loads(seen[0].content)
    assert seen[0].headers["authorization"] == "Bearer sk-1"
    assert (body["max_output_tokens"], body["temperature"]) == (64, 0.2)


async def test_an_api_key_sends_a_cache_key_only_where_the_host_takes_one() -> None:
    """A strict endpoint rejects a field it does not know, so only OpenAI's own gets it."""
    bodies: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        bodies[request.url.host] = json.loads(request.content)
        return httpx.Response(200, text=_text("ok"))

    for base in ("https://api.sakana.ai/v1", "https://api.openai.com/v1"):
        provider = ResponsesChatProvider(
            base, ApiKey("sk-1"), transport=httpx.MockTransport(handler)
        )
        async for _ in provider.chat(
            "fugu", [Message("user", "hi")], conversation="thread-7"
        ):
            pass

    assert "prompt_cache_key" not in bodies["api.sakana.ai"]
    assert bodies["api.openai.com"]["prompt_cache_key"] == "thread-7"


async def test_a_refused_api_key_is_a_refused_key_not_a_sign_in() -> None:
    """A key has nothing to refresh, so its 401 is the endpoint's, sorted by status."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    provider = ResponsesChatProvider(
        BASE, ApiKey("sk-1"), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(httpx.HTTPStatusError, match="bad key"):
        async for _ in provider.chat("fugu", [Message("user", "hi")]):
            pass

    assert len(seen) == 1


async def test_a_plans_window_is_what_its_model_list_says() -> None:
    """The plan states each model's window; one it leaves out stays unknown."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "gpt-5", "visibility": "list", "context_window": 272000},
                    {"slug": "gpt-mini", "visibility": "list"},
                ]
            },
        )

    provider = _provider(handler)

    assert await provider.context_tokens("gpt-5") == 272000
    assert await provider.context_tokens("gpt-mini") is None


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


class Pauses:
    """The waits between retries, recorded instead of slept."""

    def __init__(self) -> None:
        self.waited: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waited.append(seconds)


def _answering(*statuses: int, headers: dict | None = None):
    """Refuse with each status in turn, then answer."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) <= len(statuses):
            return httpx.Response(
                statuses[len(seen) - 1],
                json={"error": {"message": "busy"}},
                headers=headers or {},
            )
        return httpx.Response(200, text=_text("Hel", "lo"))

    return handler, seen


async def test_a_brief_throttle_is_retried_after_the_wait_it_asks_for() -> None:
    """A moment's throttling is waited out instead of failing the reply."""
    handler, seen = _answering(429, headers={"retry-after": "1"})
    pauses = Pauses()
    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pauses,
    )

    answer = "".join([t async for t in provider.chat("gpt-5", [Message("user", "hi")])])

    assert answer == "Hello"
    assert pauses.waited == [1.0]
    assert len(seen) == 2


async def test_a_wait_stated_in_milliseconds_is_honoured() -> None:
    """The finer of the two headers wins when the endpoint sends it."""
    handler, _seen = _answering(503, headers={"retry-after-ms": "1500"})
    pauses = Pauses()
    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pauses,
    )

    async for _ in provider.chat("gpt-5", [Message("user", "hi")]):
        pass

    assert pauses.waited == [1.5]


async def test_a_long_wait_is_capped_at_a_minute() -> None:
    """A reply never sits silent for minutes on the endpoint's say-so."""
    handler, _seen = _answering(429, headers={"retry-after": "300"})
    pauses = Pauses()
    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pauses,
    )

    async for _ in provider.chat("gpt-5", [Message("user", "hi")]):
        pass

    assert pauses.waited == [60.0]


async def test_it_gives_up_after_two_retries_with_the_last_status() -> None:
    """A failure that outlasts two waits is the run's failure, kept as it is."""
    handler, seen = _answering(503, 503, 503)
    pauses = Pauses()
    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pauses,
    )

    with pytest.raises(httpx.HTTPStatusError) as failed:
        async for _ in provider.chat("gpt-5", [Message("user", "hi")]):
            pass

    assert failed.value.response.status_code == 503
    assert pauses.waited == [1.0, 2.0]
    assert len(seen) == 3


async def test_a_used_up_plan_is_never_retried() -> None:
    """No wait clears it: the plan's limit resets on its own schedule."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": "subscription_sharing_usage_limit_exceeded",
                    "message": "Limit.",
                }
            },
        )

    pauses = Pauses()
    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pauses,
    )

    with pytest.raises(PlanLimitError):
        async for _ in provider.chat("gpt-5", [Message("user", "hi")]):
            pass

    assert (pauses.waited, len(seen)) == ([], 1)


async def test_stopping_during_a_wait_sends_nothing_more() -> None:
    """Stop ends the wait at once, without a request it no longer wants."""
    import asyncio

    handler, seen = _answering(429, headers={"retry-after": "30"})
    waiting = asyncio.Event()

    async def pause(_seconds: float) -> None:
        waiting.set()
        await asyncio.Event().wait()

    provider = ResponsesChatProvider(
        BASE,
        PlanToken(Tokens("t1")),
        transport=httpx.MockTransport(handler),
        pause=pause,
    )

    async def consume() -> None:
        async for _ in provider.chat("gpt-5", [Message("user", "hi")]):
            pass

    task = asyncio.create_task(consume())
    await waiting.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(seen) == 1
