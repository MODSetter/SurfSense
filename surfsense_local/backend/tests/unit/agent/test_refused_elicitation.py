"""A server never learns the runtime could ask the user for input, which SurfSense shows no form for."""

import json

import pytest

from modules.agent.plugin_gateway.refused_elicitation import without_elicitation

pytestmark = pytest.mark.unit


def _initialize(capabilities: dict) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": capabilities,
                "clientInfo": {"name": "opencode", "version": "2.1.2"},
            },
        }
    ).encode()


def test_opencode_s_offer_to_ask_is_taken_out() -> None:
    """Everything else it offers, and who it is, reach the server as sent."""
    sent = json.loads(
        without_elicitation(_initialize({"elicitation": {}, "roots": {}}))
    )

    assert sent["params"]["capabilities"] == {"roots": {}}
    assert sent["params"]["clientInfo"]["name"] == "opencode"


@pytest.mark.parametrize(
    "body",
    [
        _initialize({"roots": {}}),
        b'{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"elicitation": 1}}',
        b"not json",
    ],
)
def test_anything_else_passes_as_it_came(body: bytes) -> None:
    """Only an `initialize` offering elicitation is changed."""
    assert without_elicitation(body) == body
