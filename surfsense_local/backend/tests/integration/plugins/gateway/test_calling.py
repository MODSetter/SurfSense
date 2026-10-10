import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.gateway.calling import call_tool
from modules.plugins.gateway.scope import Scope
from modules.plugins.results.models import PluginCall, PluginCaller, PluginCallStatus
from modules.workspaces.models import Workspace
from tests.integration.plugins.gateway.conftest import FakeSource, connect, tool

pytestmark = pytest.mark.integration


@pytest.fixture
def scope(session: Session) -> Scope:
    """The first workspace, made if the database has none."""
    workspace = session.scalars(select(Workspace)).first()
    if workspace is None:
        workspace = Workspace(name="Test")
        session.add(workspace)
        session.commit()
    return Scope(workspace_id=workspace.id, thread_id=7, message_id=None)


async def never_asked(ready_tool, arguments) -> bool:
    """An approver that fails the test if the call asks for approval."""
    raise AssertionError("this call should not need approval")


async def test_a_call_returns_its_result_and_records_it_whole(
    session: Session, scope: Scope
) -> None:
    """The caller gets the result, and the call stays in the thread's record."""
    source = FakeSource([tool("search", readOnlyHint=True)], answer="three notes")
    await connect(session, "notes", source)

    outcome = await call_tool(
        session,
        scope,
        "notes__search",
        {"query": "plans"},
        caller=PluginCaller.AGENT,
        source_for=lambda plugin: source,
        approve=never_asked,
    )

    assert outcome.text == "three notes"
    assert source.calls == [("search", {"query": "plans"})]
    call = session.get(PluginCall, outcome.call_id)
    assert call.status == PluginCallStatus.SUCCEEDED
    assert (call.plugin_id, call.tool, call.arguments) == (
        "notes",
        "search",
        {"query": "plans"},
    )
    assert call.result_text == "three notes"
    assert call.thread_id == 7


async def calling(
    session: Session, scope: Scope, source: FakeSource, name: str, arguments
):
    """Call `name` as the agent, with no approval expected."""
    return await call_tool(
        session,
        scope,
        name,
        arguments,
        caller=PluginCaller.AGENT,
        source_for=lambda plugin: source,
        approve=never_asked,
    )


async def test_arguments_that_break_the_schema_are_refused_and_nothing_is_called(
    session: Session, scope: Scope
) -> None:
    """A model's bad arguments never reach the server, and leave no call behind."""
    source = FakeSource([tool("search", readOnlyHint=True)])
    await connect(session, "notes", source)

    outcome = await calling(session, scope, source, "notes__search", {"query": 3})

    assert outcome.status == PluginCallStatus.FAILED
    assert outcome.call_id is None
    assert "query" in outcome.text
    assert source.calls == []
    assert session.scalars(select(PluginCall)).all() == []


async def test_a_tool_that_is_not_ready_is_refused_with_a_sentence(
    session: Session, scope: Scope
) -> None:
    """An unknown or switched-off tool is a sentence for the model, never an exception."""
    source = FakeSource([tool("search", readOnlyHint=True)])
    await connect(session, "notes", source)

    outcome = await calling(session, scope, source, "notes__delete", {})

    assert outcome.status == PluginCallStatus.FAILED
    assert "notes__delete" in outcome.text
    assert source.calls == []


async def test_a_long_result_reaches_the_model_trimmed_and_is_kept_whole(
    session: Session, scope: Scope
) -> None:
    """20 KB is what a model gets; the step shows all of it from the record."""
    long_text = "a" * 30_000 + "b" * 30_000
    source = FakeSource([tool("search", readOnlyHint=True)], answer=long_text)
    await connect(session, "notes", source)

    outcome = await calling(session, scope, source, "notes__search", {"query": "x"})

    assert len(outcome.text.encode()) <= 20_000
    assert outcome.text.startswith("aaa")
    assert outcome.text.endswith("bbb")
    assert "characters cut" in outcome.text
    assert session.get(PluginCall, outcome.call_id).result_text == long_text


async def test_a_source_that_fails_ends_the_call_failed_with_a_sentence(
    session: Session, scope: Scope
) -> None:
    """A server that breaks mid-call is recorded, and the model reads why."""
    source = FakeSource(
        [tool("search", readOnlyHint=True)],
        answer=RuntimeError("the plugin's server answered 503"),
    )
    await connect(session, "notes", source)

    outcome = await calling(session, scope, source, "notes__search", {"query": "x"})

    assert outcome.status == PluginCallStatus.FAILED
    assert "503" in outcome.text
    call = session.get(PluginCall, outcome.call_id)
    assert call.status == PluginCallStatus.FAILED
    assert call.error == "the plugin's server answered 503"
    assert call.finished_at is not None
