"""The Claude plan connection: Claude Code's state, and the connection made from it."""

import pytest
from httpx import AsyncClient

from tests.claude_stand_in import SIGNED_OUT

from .conftest import ClaudeOnThisMachine, FakeClaude

pytestmark = pytest.mark.integration
ANTHROPIC = "host:api.anthropic.com"


async def _allow_anthropic(client: AsyncClient) -> None:
    reply = await client.put(f"/egress/{ANTHROPIC}", json={"enabled": True})
    assert reply.status_code == 200


async def _connect(client: AsyncClient) -> dict:
    await _allow_anthropic(client)
    reply = await client.post("/llm/connections/claude", json={"label": "Claude"})
    assert reply.status_code == 201, reply.text
    return reply.json()


async def test_a_machine_without_claude_code_says_so(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """The dialog's first view: install Claude Code."""
    claude_on_this_machine(installed=False)

    option = (await client.get("/llm/connections/claude")).json()

    assert option["state"] == "not_installed"
    assert option["serves"] == ["text_gen"]
    assert option["hosts"] == [{"destination": ANTHROPIC, "host": "api.anthropic.com"}]


async def test_a_signed_in_claude_code_is_ready_with_its_account(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Read live each time, so signing in or out in a terminal shows on the next look."""
    claude_on_this_machine()

    option = (await client.get("/llm/connections/claude")).json()

    assert option["state"] == "ready"
    assert option["email"] == "ada@example.com"
    assert option["plan"] == "max"
    assert option["version"] == "2.1.301"


@pytest.mark.parametrize(
    ("stand_in", "state"),
    [
        ({"auth": SIGNED_OUT}, "signed_out"),
        ({"version": "2.0.12 (Claude Code)"}, "too_old"),
    ],
)
async def test_a_claude_code_that_is_not_ready_says_what_to_do(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    stand_in: dict,
    state: str,
) -> None:
    """Each state is one thing the user does in their terminal."""
    claude_on_this_machine(**stand_in)

    assert (await client.get("/llm/connections/claude")).json()["state"] == state


async def test_an_allowed_host_is_not_asked_about_again(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Once api.anthropic.com is on, the dialog has nothing left to ask."""
    claude_on_this_machine()
    await _allow_anthropic(client)

    assert (await client.get("/llm/connections/claude")).json()["hosts"] == []


async def test_a_ready_claude_code_makes_a_claude_plan_connection(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """It holds no credential: Claude Code keeps the sign-in."""
    claude_on_this_machine()

    connection = await _connect(client)

    assert connection["auth_kind"] == "claude_plan"
    assert connection["base_url"] == "https://api.anthropic.com"
    assert connection["catalog_provider"] == "anthropic"
    assert connection["has_api_key"] is False
    assert connection["serves"] == ["text_gen"]


async def test_connecting_asks_for_anthropic_first(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Every model call goes to api.anthropic.com, so its egress comes first."""
    claude_on_this_machine()

    reply = await client.post("/llm/connections/claude", json={"label": "Claude"})

    assert reply.status_code == 403
    assert reply.json()["detail"]["destination"] == ANTHROPIC


async def test_a_claude_code_that_is_not_ready_cannot_connect(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Refused with the state, so the dialog can show what to do instead."""
    claude_on_this_machine(auth=SIGNED_OUT)
    await _allow_anthropic(client)

    reply = await client.post("/llm/connections/claude", json={"label": "Claude"})

    assert reply.status_code == 422
    assert reply.json()["detail"]["state"] == "signed_out"


async def test_there_is_one_claude_plan_per_install(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Claude Code holds one sign-in, so a second connection would be the same plan."""
    claude_on_this_machine()
    await _connect(client)

    reply = await client.post("/llm/connections/claude", json={"label": "Another"})

    assert reply.status_code == 409


async def test_the_connection_lists_claude_codes_models(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Each model once, by its full id, so the manifest's capabilities apply to it."""
    claude_on_this_machine()
    connection = await _connect(client)

    reply = await client.get(f"/llm/connections/{connection['id']}/models")

    assert reply.status_code == 200, reply.text
    listed = {m["name"]: m for m in reply.json()}
    assert sorted(listed) == [
        "claude-fable-5-1",
        "claude-haiku-5-5",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
    ]
    assert listed["claude-sonnet-5-5"]["selectable_for"] == ["text_gen"]


async def test_a_claude_plan_can_be_renamed_and_nothing_else(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Its address and sign-in are Claude Code's; only the name is the user's."""
    claude_on_this_machine()
    connection = await _connect(client)

    reply = await client.put(
        f"/llm/connections/{connection['id']}",
        json={
            "label": "My Claude",
            "provider": "openai_compatible",
            "base_url": "https://evil.example/v1",
            "api_key": "sk-x",
        },
    )

    assert reply.status_code == 200, reply.text
    assert reply.json()["label"] == "My Claude"
    assert reply.json()["base_url"] == "https://api.anthropic.com"
    assert reply.json()["has_api_key"] is False


async def test_a_claude_plan_can_be_removed(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Removing it leaves Claude Code's own sign-in alone."""
    claude_on_this_machine()
    connection = await _connect(client)

    reply = await client.delete(f"/llm/connections/{connection['id']}")

    assert reply.status_code == 204
    listed = (await client.get("/llm/connections")).json()
    assert all(c["id"] != connection["id"] for c in listed)


async def test_a_plan_whose_claude_code_is_gone_asks_to_set_it_up_again(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine, tmp_path
) -> None:
    """Uninstalled after connecting: the picker says why, rather than failing."""
    installed = claude_on_this_machine()
    connection = await _connect(client)
    installed.unlink()

    reply = await client.get(f"/llm/connections/{connection['id']}/models")

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "sign_in_required"
