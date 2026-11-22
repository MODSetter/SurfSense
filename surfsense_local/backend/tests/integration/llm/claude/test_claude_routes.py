"""The Claude plan connection: Claude Code's state, and the connection made from it."""

import pytest
from httpx import AsyncClient

from tests.claude_stand_in import SIGNED_OUT

from .conftest import ClaudeOnThisMachine, FakeClaude

pytestmark = pytest.mark.integration
ANTHROPIC = "host:api.anthropic.com"
SIGN_IN = "host:platform.claude.com"


async def _allow(client: AsyncClient, *destinations: str) -> None:
    for destination in destinations:
        reply = await client.put(
            "/egress", json={"destinations": [destination], "enabled": True}
        )
        assert reply.status_code == 200


async def _allow_anthropic(client: AsyncClient) -> None:
    await _allow(client, ANTHROPIC, SIGN_IN)


async def _connect(client: AsyncClient) -> dict:
    await _allow_anthropic(client)
    reply = await client.post("/llm/connections/claude", json={"label": "Claude"})
    assert reply.status_code == 201, reply.text
    return reply.json()


async def test_the_option_is_offered_without_running_claude_code(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine, tmp_path
) -> None:
    """The row shows at once, installed or not: what a plan fills is not Claude Code's to say."""
    runs = tmp_path / "claude-runs.json"
    claude_on_this_machine(env_log=runs)

    option = (await client.get("/llm/connections/claude")).json()

    assert option == {
        "serves": ["text_gen"],
        "hosts": [
            {"destination": ANTHROPIC, "host": "api.anthropic.com"},
            {"destination": SIGN_IN, "host": "platform.claude.com"},
        ],
    }
    assert not runs.exists()


async def test_a_machine_without_claude_code_says_so(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """The dialog's first view: install Claude Code."""
    claude_on_this_machine(installed=False)

    found = (await client.get("/llm/connections/claude/status")).json()

    assert found["state"] == "not_installed"


async def test_a_signed_in_claude_code_is_ready_with_its_account(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Read live each time, so signing in or out in a terminal shows on the next look."""
    claude_on_this_machine()

    found = (await client.get("/llm/connections/claude/status")).json()

    assert found == {
        "state": "ready",
        "version": "2.1.301",
        "email": "ada@example.com",
        "plan": "max",
    }


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

    found = await client.get("/llm/connections/claude/status")
    assert found.json()["state"] == state


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


async def test_connecting_asks_for_both_anthropic_hosts_first(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Model calls and the sign-in's refresh go to two hosts, named in one refusal."""
    claude_on_this_machine()

    reply = await client.post("/llm/connections/claude", json={"label": "Claude"})

    assert reply.status_code == 403
    detail = reply.json()["detail"]
    assert detail["destination"] == ANTHROPIC
    assert detail["hosts"] == ["api.anthropic.com", "platform.claude.com"]
    assert detail["purpose"] == "claude_plan"


async def test_one_host_allowed_still_asks_for_the_other(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """Each host is its own consent; only the one still off is asked about."""
    claude_on_this_machine()
    await _allow(client, ANTHROPIC)

    option = (await client.get("/llm/connections/claude")).json()

    assert option["hosts"] == [{"destination": SIGN_IN, "host": "platform.claude.com"}]


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
    assert reply.json()["detail"]["code"] == "claude_sign_in_required"


async def test_a_plan_whose_claude_code_is_now_too_old_says_so(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Replaced by an older one after connecting: the composer says to update before anything is sent."""
    claude_on_this_machine()
    connection = await _connect(client)
    claude_on_this_machine(version="2.1.200 (Claude Code)")

    reply = await client.get(f"/llm/connections/{connection['id']}/models")

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "claude_too_old"


async def test_a_claude_code_whose_version_cannot_be_read_still_lists(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """An answer not yet seen on another system never blocks a plan that may work."""
    claude_on_this_machine()
    connection = await _connect(client)
    claude_on_this_machine(version="Claude Code, nightly")

    reply = await client.get(f"/llm/connections/{connection['id']}/models")

    assert reply.status_code == 200, reply.text


async def test_the_model_list_needs_both_hosts(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """With the sign-in host off, the chat's model check asks for it at once,
    rather than Claude Code failing hours later when its sign-in expires."""
    claude_on_this_machine()
    connection = await _connect(client)
    await client.put("/egress", json={"destinations": [SIGN_IN], "enabled": False})

    reply = await client.get(f"/llm/connections/{connection['id']}/models")

    assert reply.status_code == 403
    assert reply.json()["detail"]["destination"] == SIGN_IN


async def test_removing_the_plan_forgets_its_sign_in_host(
    client: AsyncClient, claude_on_this_machine: ClaudeOnThisMachine
) -> None:
    """No connection names platform.claude.com, so nothing else would clear it."""
    claude_on_this_machine()
    connection = await _connect(client)

    await client.delete(f"/llm/connections/{connection['id']}")

    listed = [row["destination"] for row in (await client.get("/egress")).json()]
    assert SIGN_IN not in listed
