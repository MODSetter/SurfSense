"""Which plugin tools an opencode turn holds when they do not all fit, and how it gets more.

Past the model's share the agent holds what the request needs, sees every plugin in
SurfSense's instructions, and loads more by asking, by calling a tool it was not
given, or by a plugin call that turns the task elsewhere.
"""

import json
from collections.abc import Iterator

import pytest
from mcp.server.mcpserver import MCPServer

from modules.agent.tool_exposure import turn_tools
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import of_type, open_thread, send
from tests.integration.agent.test_plugin_tools import call, connect_notes, notes_url
from tests.mcp_test_server import serving

pytestmark = pytest.mark.integration

__all__ = ["notes_url"]

ASKS = ["surfsense_find_tools", "surfsense_open_plugin"]


@pytest.fixture
def no_room(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model window whose share for plugin tools fits none of them."""
    monkeypatch.setattr(turn_tools, "plugin_share", lambda _window: 1)


@pytest.fixture
def weather_url() -> Iterator[str]:
    """A second plugin, about something else than notes."""
    server = MCPServer("weather")

    @server.tool()
    def forecast(city: str) -> str:
        """The weather forecast for a city."""
        return f"sunny in {city}"

    with serving(server.streamable_http_app()) as base:
        yield f"{base}/mcp"


async def notes_without_asking(api: AgentAPI, url: str) -> None:
    """Notes connected, its search run without asking the user first."""
    await connect_notes(api, url)
    await api.http.put("/plugins/notes/tools/search", json={"approval": "always"})


def offered(api: AgentAPI, request: int) -> list[str]:
    """Every tool but opencode's own and SurfSense's, offered to one model request."""
    tools = api.model.requests[request].get("tools") or []
    names = (t["function"]["name"] for t in tools)
    return sorted(
        n
        for n in names
        if n.startswith(("notes", "weather", "surfsense_open", "surfsense_find"))
    )


def told(api: AgentAPI, request: int = 0) -> str:
    return json.dumps(api.model.requests[request]["messages"])


async def test_every_tool_is_held_while_they_all_fit(
    agent_api: AgentAPI, notes_url: str
) -> None:
    """Nothing to ask for: no catalogue, and no tools to load more."""
    await connect_notes(agent_api, notes_url)
    agent_api.model.replies = [("text", "Hi.")]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "Hello")

    assert offered(agent_api, 0) == ["notes_count", "notes_search"]
    assert "# Plugins" not in told(agent_api)


async def test_past_the_share_a_plugin_not_asked_for_is_named_in_the_catalogue(
    agent_api: AgentAPI, notes_url: str, no_room: None
) -> None:
    """The agent learns it is connected and how to load it, rather than saying it is not."""
    await connect_notes(agent_api, notes_url)
    agent_api.model.replies = [("text", "Hi.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "How many words did I write?")

    assert offered(agent_api, 0) == ASKS
    assert "Notes (@notes)" in told(agent_api)
    assert "surfsense_open_plugin" in told(agent_api)
    assert of_type(frames, "agent-plugins-unavailable") == []


async def test_a_mentioned_plugin_is_held_whole_past_the_share(
    agent_api: AgentAPI, notes_url: str, no_room: None
) -> None:
    """`@notes` is the user's choice: every ready tool of it is held, whatever they cost."""
    await connect_notes(agent_api, notes_url)
    agent_api.model.replies = [("text", "Counting.")]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "How many words? @notes")

    assert offered(agent_api, 0) == ["notes_count", "notes_search", *ASKS]
    assert "The user asked you to use the Notes plugin for this." in told(agent_api)


async def test_opening_a_plugin_holds_its_tools_from_the_next_step(
    agent_api: AgentAPI, notes_url: str, no_room: None
) -> None:
    await connect_notes(agent_api, notes_url)
    agent_api.model.replies = [
        call("surfsense_open_plugin", plugin="Notes"),
        ("text", "Done."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "How many words did I write?")

    assert offered(agent_api, 1) == ["notes_count", "notes_search", *ASKS]
    step = of_type(frames, "agent-step")[-1]
    assert (step["tool"], step["status"]) == ("surfsense_open_plugin", "completed")
    assert step["loaded_plugin"] == "Notes"


async def test_finding_tools_holds_the_plugin_of_the_best_one(
    agent_api: AgentAPI, notes_url: str, weather_url: str, no_room: None
) -> None:
    await connect_notes(agent_api, notes_url)
    added = await agent_api.http.post(
        "/plugins/custom", json={"url": weather_url, "name": "Weather"}
    )
    assert added.status_code == 201, added.text
    agent_api.model.replies = [
        call("surfsense_find_tools", query="the forecast for a city"),
        ("text", "Done."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Will it rain?")

    assert offered(agent_api, 1) == [*ASKS, "weather_forecast"]
    # The thread reads it as loading the plugin, by the plugin's name, live and read back.
    assert of_type(frames, "agent-step")[-1]["loaded_plugin"] == "Weather"
    listed = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
    (found,) = listed.json()[-1]["content"]["steps"]
    assert found["loaded_plugin"] == "Weather"


async def test_a_call_to_a_tool_not_held_loads_its_plugin_and_says_so(
    agent_api: AgentAPI, notes_url: str, no_room: None
) -> None:
    """opencode refuses it and goes straight on; the step reads as loading the plugin,
    and is read back so. The rules reach opencode after that next step began, so the
    plugin's tools are the agent's from the step after it."""
    await notes_without_asking(agent_api, notes_url)
    agent_api.model.replies = [
        call("notes_search", query="ship"),
        call("surfsense_search_sources", query="ship"),
        call("notes_search", query="ship"),
        ("text", "Found it."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "When do we ship?")

    assert offered(agent_api, 0) == ASKS
    assert offered(agent_api, 2) == ["notes_count", "notes_search", *ASKS]
    # Each step as it finished; the scripted model numbers every call call_1.
    finished = [
        f
        for f in of_type(frames, "agent-step")
        if f["status"] in ("completed", "error")
    ]
    loaded, _, searched = finished
    assert loaded["tool"] == "surfsense_loaded_tools"
    assert (loaded["status"], loaded["loaded_plugin"]) == ("completed", "Notes")
    assert (searched["tool"], searched["status"]) == ("notes_search", "completed")
    listed = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
    steps = listed.json()[-1]["content"]["steps"]
    assert [s["tool"] for s in steps] == [
        "surfsense_loaded_tools",
        "surfsense_search_sources",
        "notes_search",
    ]
    assert steps[0]["loaded_plugin"] == "Notes"


async def test_a_plugin_call_never_holds_another_plugin(
    agent_api: AgentAPI, notes_url: str, weather_url: str, no_room: None
) -> None:
    """The request turns to the forecast, but Weather comes only through the
    catalogue or by asking: a guess after each call was mostly wrong."""
    await notes_without_asking(agent_api, notes_url)
    added = await agent_api.http.post(
        "/plugins/custom", json={"url": weather_url, "name": "Weather"}
    )
    assert added.status_code == 201, added.text
    agent_api.model.replies = [
        call("notes_search", query="trip city"),
        ("text", "Done."),
    ]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "Find my trip in @notes and check the forecast")

    assert offered(agent_api, 0) == ["notes_count", "notes_search", *ASKS]
    assert offered(agent_api, 1) == ["notes_count", "notes_search", *ASKS]
