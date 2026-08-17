from contextlib import asynccontextmanager
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.middleware import (
    artifact_roster,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.middleware.artifact_roster import (
    ArtifactRosterMiddleware,
)


async def test_roster_resolves_each_chat_from_live_config(monkeypatch):
    class Result:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class Session:
        async def execute(self, statement):
            values = {str(value) for value in statement.compile().params.values()}
            if "101" in values:
                return Result([(1, 2, "markdown", "First", None)])
            if "202" in values:
                return Result([(2, 4, "pdf", "Second", "second.pdf")])
            return Result([])

    @asynccontextmanager
    async def session_context():
        yield Session()

    monkeypatch.setattr(artifact_roster, "shielded_async_session", session_context)
    middleware = ArtifactRosterMiddleware(workspace_id=7)
    state = {"messages": [HumanMessage(content="Revise it")]}

    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {"configurable": {"thread_id": "101::task:call-a"}},
    )
    first = await middleware.abefore_agent(state, SimpleNamespace())
    assert "artifact_id=1" in first["messages"][0].content
    assert "generation=2" in first["messages"][0].content
    assert "format=markdown" in first["messages"][0].content
    assert "artifact_id=2" not in first["messages"][0].content

    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {"configurable": {"thread_id": "202::task:call-b"}},
    )
    second = await middleware.abefore_agent(state, SimpleNamespace())
    assert "artifact_id=2" in second["messages"][0].content
    assert "generation=4" in second["messages"][0].content
    assert "format=pdf" in second["messages"][0].content
    assert "artifact_id=1" not in second["messages"][0].content
