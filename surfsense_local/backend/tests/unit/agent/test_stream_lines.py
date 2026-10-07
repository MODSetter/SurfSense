"""The agent's streams keep a line holding U+2028, U+2029 or U+0085 whole.

opencode and the model leave those raw inside a JSON string: a tool's output
read from a Word file or a PDF can carry them.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from modules.agent.model_endpoint.model_address import ModelAddress
from modules.agent.model_endpoint.relay import CHAT_COMPLETIONS, RESPONSES, Wire, relay
from modules.agent.opencode_client.events import read_events

pytestmark = pytest.mark.unit

SEPARATED = "line one\u2028line two\u2029para\x85next"
_REAL_CLIENT = httpx.AsyncClient


def _streaming(chunks: list[bytes]) -> httpx.MockTransport:
    async def body() -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    return httpx.MockTransport(lambda _: httpx.Response(200, content=body()))


def _cut_at_every(data: bytes, size: int) -> list[bytes]:
    """Reads of `size` bytes, which cut separators, lines and the end marker apart."""
    return [data[at : at + size] for at in range(0, len(data), size)]


async def test_a_tool_output_holding_separators_is_one_event() -> None:
    """Half an event used to fail to parse and end the turn with an error."""
    event = {
        "type": "message.part.updated",
        "properties": {
            "sessionID": "ses_1",
            "part": {
                "type": "tool",
                "state": {"status": "completed", "output": SEPARATED},
            },
        },
    }
    stream = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()

    async with _REAL_CLIENT(
        base_url="http://opencode", transport=_streaming(_cut_at_every(stream, 7))
    ) as http:
        (read,) = [e async for e in read_events(http, Path("."))]

    assert read.properties["part"]["state"]["output"] == SEPARATED


async def _relayed(
    monkeypatch: pytest.MonkeyPatch, chunks: list[bytes], wire: Wire
) -> bytes:
    """What opencode reads from the relay while the model sends `chunks`."""
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **options: _REAL_CLIENT(transport=_streaming(chunks), **options),
    )
    released: list[bool] = []

    async def done() -> None:
        released.append(True)

    address = ModelAddress("http://model/v1/chat/completions", {}, "m", ("m",))
    reply = await relay(address, {"stream": True}, done, wire=wire)
    relayed = b"".join([piece async for piece in reply.body_iterator])

    assert released == [True]
    return relayed


async def test_a_chat_stream_reaches_opencode_byte_for_byte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing re-split, and `[DONE]` across two reads still ends it, so no
    second one is added."""
    chunk = {"choices": [{"delta": {"content": SEPARATED}}]}
    stream = (
        f"data: {json.dumps(chunk, ensure_ascii=False)}\r\n\r\ndata: [DONE]\n\n"
    ).encode()

    for size in (1, 5, 13, len(stream)):
        relayed = await _relayed(
            monkeypatch, _cut_at_every(stream, size), CHAT_COMPLETIONS
        )

        assert relayed == stream


async def test_a_responses_stream_ending_across_two_reads_is_not_called_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only its terminal event ends it; read whole, it is seen."""
    events = [
        {"type": "response.output_text.delta", "delta": SEPARATED},
        {"type": "response.completed", "response": {"status": "completed"}},
    ]
    stream = "".join(
        f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
        for e in events
    ).encode()

    for size in (3, 11, len(stream)):
        relayed = await _relayed(monkeypatch, _cut_at_every(stream, size), RESPONSES)

        assert relayed == stream


async def test_a_stream_that_stops_unended_is_still_told_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Responses stream cut before its terminal event reads as a failure."""
    event = {"type": "response.output_text.delta", "delta": "Half"}
    stream = f"data: {json.dumps(event)}\n\n".encode()

    relayed = await _relayed(monkeypatch, _cut_at_every(stream, 4), RESPONSES)

    assert relayed.startswith(stream)
    assert b"the model stopped before finishing its reply" in relayed[len(stream) :]
