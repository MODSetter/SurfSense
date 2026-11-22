import pytest
from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import PluginSettings, PluginTool
from tests.integration.plugins.gateway.conftest import FakeSource, connect, tool

pytestmark = pytest.mark.integration


async def test_a_connected_plugins_tools_are_listed_by_qualified_name(
    session: Session,
) -> None:
    """Every caller names a tool `<plugin>__<tool>`, whatever the source."""
    await connect(session, "notes", FakeSource([tool("search"), tool("read")]))

    listed = list_tools(session)

    assert [t.qualified_name for t in listed] == ["notes__search", "notes__read"]
    assert listed[0].plugin_name == "Notes"
    assert listed[0].description == "The search tool."


async def test_a_tool_switched_off_is_not_listed(session: Session) -> None:
    """The user's switch on a tool is final for every caller."""
    await connect(session, "notes", FakeSource([tool("search"), tool("delete")]))
    session.get(PluginTool, ("notes", "delete")).enabled = False
    session.commit()

    assert [t.tool for t in list_tools(session)] == ["search"]


async def test_third_party_plugins_wait_until_the_user_allows_them(
    session: Session,
) -> None:
    """Only first-party plugins are offered until the user allows third-party ones."""
    await connect(session, "notion", FakeSource([tool("search")]), first_party=False)

    assert list_tools(session) == []

    session.add(PluginSettings(id=1, third_party_on=True))
    session.commit()

    assert [t.qualified_name for t in list_tools(session)] == ["notion__search"]


async def test_a_plugin_whose_host_is_not_allowed_offers_nothing(
    session: Session,
) -> None:
    """A host revoked in Settings > Network takes the plugin's tools away."""
    await connect(
        session,
        "scrapers",
        FakeSource([tool("crawl")]),
        url="https://plugins.example/mcp",
    )

    assert list_tools(session) == []

    session.add(EgressDestination(destination="host:plugins.example", enabled=True))
    session.commit()

    assert [t.tool for t in list_tools(session)] == ["crawl"]


async def test_names_that_collide_once_sanitised_stay_distinct(
    session: Session,
) -> None:
    """`a-b` and `a_b` would both become `a_b`; each tool still needs its own name."""
    await connect(session, "a-b", FakeSource([tool("c")]))
    await connect(session, "a_b", FakeSource([tool("c")]))

    names = [t.qualified_name for t in list_tools(session)]

    assert len(names) == 2
    assert len(set(names)) == 2
    assert names[0] == "a_b__c"
