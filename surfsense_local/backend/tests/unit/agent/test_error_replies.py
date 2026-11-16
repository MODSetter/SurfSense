"""A model's error, as opencode will show it: always a sentence under `error.message`."""

import json

import pytest

from modules.agent.model_endpoint.error_replies import as_error_body

pytestmark = pytest.mark.unit


def _message(content: bytes, status: int = 400) -> str:
    return json.loads(as_error_body(content, status))["error"]["message"]


def test_a_plans_detail_is_shown_as_its_sentence() -> None:
    """The ChatGPT plan words a field it does not take as `detail`; opencode would show the JSON."""
    refused = b'{"detail": "Unsupported parameter: max_output_tokens"}'

    assert _message(refused) == "Unsupported parameter: max_output_tokens"


def test_an_error_with_a_message_passes_as_it_came() -> None:
    """opencode reads a full window from a model's own words."""
    content = json.dumps(
        {"error": {"message": "exceeds the available context size", "code": 400}}
    ).encode()

    assert as_error_body(content, 400) == content


@pytest.mark.parametrize(
    ("content", "said"),
    [
        (b'{"error": "rate limited"}', "rate limited"),
        (b"Bad gateway", "Bad gateway"),
        (b"", "the model answered 502"),
    ],
)
def test_anything_else_becomes_a_message(content: bytes, said: str) -> None:
    """A bare string, plain text, or nothing at all."""
    assert _message(content, 502) == said
