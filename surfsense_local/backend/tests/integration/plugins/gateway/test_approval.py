import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.gateway.calling import call_tool
from modules.plugins.gateway.scope import Scope
from modules.plugins.installed.models import PluginSettings, PluginTool, ToolApproval
from modules.plugins.results.models import PluginCall, PluginCaller, PluginCallStatus
from modules.workspaces.models import Workspace
from tests.integration.plugins.gateway.conftest import FakeSource, connect, tool

pytestmark = pytest.mark.integration


class Asker:
    """Stands in for the user: answers every approval the same way, and counts them."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def __call__(self, ready_tool, arguments) -> bool:
        self.asked.append(ready_tool.qualified_name)
        return self.answer


@pytest.fixture
def scope(session: Session) -> Scope:
    """A workspace with third-party plugins allowed, so they can be called."""
    workspace = Workspace(name="Test")
    session.add(workspace)
    session.add(PluginSettings(id=1, third_party_on=True))
    session.commit()
    return Scope(workspace_id=workspace.id, thread_id=1, message_id=None)


async def call(session: Session, scope: Scope, source: FakeSource, asker: Asker):
    """Call the one connected tool, answering approval with `asker`."""
    return await call_tool(
        session,
        scope,
        f"{session.scalars(select(PluginTool)).first().plugin_id}__"
        f"{source.tools[0].name}",
        {"query": "x"},
        caller=PluginCaller.AGENT,
        source_for=lambda plugin: source,
        approve=asker,
    )


def always_allow(session: Session) -> None:
    """Set every recorded tool to Always allow, as the user would."""
    for row in session.scalars(select(PluginTool)):
        row.approval = ToolApproval.ALWAYS
    session.commit()


async def test_a_third_partys_read_only_tool_still_asks(
    session: Session, scope: Scope
) -> None:
    """A server's read-only annotation is its own claim, trusted only from SurfSense's."""
    source = FakeSource([tool("search", readOnlyHint=True)])
    await connect(session, "notion", source, publisher="partner")
    asker = Asker(answer=False)

    outcome = await call(session, scope, source, asker)

    assert asker.asked == ["notion__search"]
    assert outcome.status == PluginCallStatus.DENIED
    assert source.calls == []
    recorded = session.get(PluginCall, outcome.call_id)
    assert recorded.status == PluginCallStatus.DENIED


async def test_always_allow_skips_asking_for_a_tool_that_is_not_destructive(
    session: Session, scope: Scope
) -> None:
    """Once the user picks Always allow, a safe tool runs without asking."""
    source = FakeSource([tool("search", readOnlyHint=False, destructiveHint=False)])
    await connect(session, "notion", source, publisher="partner")
    always_allow(session)
    asker = Asker(answer=False)

    outcome = await call(session, scope, source, asker)

    assert asker.asked == []
    assert outcome.status == PluginCallStatus.SUCCEEDED


async def test_a_destructive_tool_asks_every_time_even_when_always_allowed(
    session: Session, scope: Scope
) -> None:
    """Deleting or overwriting is confirmed on each call, whatever was picked before."""
    source = FakeSource([tool("delete", destructiveHint=True)])
    await connect(session, "notion", source, publisher="partner")
    always_allow(session)
    asker = Asker(answer=True)

    outcome = await call(session, scope, source, asker)

    assert asker.asked == ["notion__delete"]
    assert outcome.status == PluginCallStatus.SUCCEEDED


async def test_a_tool_with_no_annotations_is_treated_as_destructive(
    session: Session, scope: Scope
) -> None:
    """MCP's defaults: a tool that says nothing may write and may destroy."""
    source = FakeSource([tool("act")])
    await connect(session, "notion", source, publisher="partner")
    always_allow(session)
    asker = Asker(answer=True)

    await call(session, scope, source, asker)

    assert asker.asked == ["notion__act"]
