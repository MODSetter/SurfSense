"""A server's voices, asked of the server: nothing is kept in the repo."""

import httpx
import pytest

from modules.llm.providers.openai_compatible.voice_list import listed_voices

pytestmark = pytest.mark.unit


def ask(handler, connection_id: int = 1):
    """The voices the server behind `handler` lists, or None."""
    return listed_voices(
        connection_id,
        f"http://tts-{connection_id}/v1",
        "secret",
        transport=httpx.MockTransport(handler),
    )


def test_a_server_that_lists_its_voices_fills_the_picker() -> None:
    """Kokoro-FastAPI's shape. It states ids alone, so no gender or language
    is given: the brief does not claim one for them."""
    seen: list[httpx.Request] = []

    def kokoro(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"voices": [{"id": "af_heart"}, {"id": "am_adam"}]}
        )

    voices = ask(kokoro, connection_id=1)

    assert str(seen[0].url) == "http://tts-1/v1/audio/voices"
    assert seen[0].headers["authorization"] == "Bearer secret"
    assert [(v.id, v.label, v.gender, v.languages) for v in voices] == [
        ("af_heart", "af_heart", None, ()),
        ("am_adam", "am_adam", None, ()),
    ]


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(404),
        httpx.Response(200, json={"data": []}),
        httpx.Response(200, json={"voices": [{"name": "no id"}]}),
        httpx.Response(200, text="<html>"),
    ],
)
def test_a_server_that_cannot_list_them_leaves_the_user_to_type_them(
    reply: httpx.Response,
) -> None:
    """OpenAI, Groq and OpenRouter have no such route: nothing is guessed."""
    assert ask(lambda request: reply, connection_id=2) is None


def test_the_answer_is_asked_once_per_server() -> None:
    """Held for the process and never stored, so the next start asks again."""
    calls: list[int] = []

    def server(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    ask(server, connection_id=3)
    ask(server, connection_id=3)

    assert calls == [1]


def test_an_unreachable_server_is_asked_again_next_time() -> None:
    """No answer is not an answer: it says nothing about the route."""
    calls: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("down")
        return httpx.Response(200, json={"voices": [{"id": "af_heart"}]})

    assert ask(flaky, connection_id=4) is None
    assert [v.id for v in ask(flaky, connection_id=4)] == ["af_heart"]
