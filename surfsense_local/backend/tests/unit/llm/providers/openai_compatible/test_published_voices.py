"""The voices a server publishes per model in its model list."""

import httpx
import pytest

from modules.llm.providers.openai_compatible.published_voices import (
    published_voices,
)

pytestmark = pytest.mark.unit


def listing(*entries: dict):
    """A server answering /models with `entries`, as OpenRouter does."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": list(entries)})

    return handler


def ask(handler, connection_id: int, model: str = "m"):
    """The voices `model` publishes on the server behind `handler`, or None."""
    return published_voices(
        connection_id,
        f"http://models-{connection_id}/v1",
        "secret",
        model,
        transport=httpx.MockTransport(handler),
    )


def test_a_model_gets_the_voices_it_publishes_and_no_other_models() -> None:
    """Each model has its own, as `supported_voices` states them."""
    handler = listing(
        {"id": "a", "supported_voices": ["sarah", "george"]},
        {"id": "b", "supported_voices": ["ava"]},
    )

    assert ask(handler, 1, "a") == ["sarah", "george"]
    assert ask(handler, 1, "b") == ["ava"]


def test_a_model_publishing_none_has_no_answer() -> None:
    """Fish Audio's on OpenRouter state none, and a model may not be listed."""
    handler = listing({"id": "m"}, {"id": "n", "supported_voices": []})

    assert ask(handler, 2, "m") is None
    assert ask(handler, 2, "n") is None
    assert ask(handler, 2, "absent") is None


def test_what_cannot_be_a_voice_id_is_left_out() -> None:
    """A voice test and a brief take ids of at most 100 characters."""
    handler = listing(
        {"id": "m", "supported_voices": ["sarah", "", 7, "x" * 101, "sarah", "will"]}
    )

    assert ask(handler, 3) == ["sarah", "will"]


def test_one_listing_answers_every_model_of_a_connection() -> None:
    """A listing holds hundreds of models, so it is read once per process."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"data": [{"id": "m", "supported_voices": ["sarah"]}]}
        )

    assert ask(handler, 4) == ["sarah"]
    assert ask(handler, 4, "other") is None
    assert len(seen) == 1
    # Its speech models are absent from OpenRouter's default listing.
    assert seen[0].url.params["output_modalities"] == "all"
    assert seen[0].headers["authorization"] == "Bearer secret"


def test_a_failed_listing_is_asked_again() -> None:
    """A failure says nothing about the voices, so it is not held."""
    answers = [
        httpx.Response(503),
        httpx.Response(200, json={"data": [{"id": "m", "supported_voices": ["a"]}]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return answers.pop(0)

    assert ask(handler, 5) is None
    assert ask(handler, 5) == ["a"]


def test_an_unreachable_server_has_no_answer() -> None:
    """The user's added voices then stand, so nothing fails here."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    assert ask(handler, 6) is None


def test_a_reply_that_is_no_listing_has_no_answer() -> None:
    """A server's odd answer never reaches a picker."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "listing"])

    assert ask(handler, 7) is None
