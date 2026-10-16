"""SurfSense keeps a thread's Claude Code session, so resume and reading back never need ~/.claude."""

import pytest
from sqlalchemy import Engine

from modules.agent.engines.claude_code.session_store import ThreadSessionStore
from modules.chat.models import AgentEngineKind, ChatThread
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration
KEY = {"project_key": "-threads-1", "session_id": "s-1"}


def _thread(engine: Engine) -> int:
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="W")
        session.add(workspace)
        session.flush()
        thread = ChatThread(
            workspace_id=workspace.id,
            agent_engine=AgentEngineKind.CLAUDE_CODE,
            claude_session_id="s-1",
        )
        session.add(thread)
        session.commit()
        return thread.id


async def test_a_session_loads_back_as_it_was_written(engine: Engine) -> None:
    """In order, each entry once, though a batch the SDK retried came twice."""
    store = ThreadSessionStore(create_session_factory(engine), _thread(engine))
    first = [{"type": "user", "uuid": "e-1"}, {"type": "queue-operation"}]
    second = [{"type": "assistant", "uuid": "e-2", "message": {"id": "msg_1"}}]

    await store.append(KEY, first)
    await store.append(KEY, second)
    await store.append(KEY, second)

    assert await store.load(KEY) == [*first, *second]


async def test_a_session_never_written_loads_as_none(engine: Engine) -> None:
    """The SDK then starts the session fresh rather than resuming an empty one."""
    store = ThreadSessionStore(create_session_factory(engine), _thread(engine))

    assert await store.load({**KEY, "session_id": "s-2"}) is None


async def test_a_subagents_transcript_is_not_kept(engine: Engine) -> None:
    """SurfSense gives Claude Code no subagents; one appearing is never the thread's."""
    store = ThreadSessionStore(create_session_factory(engine), _thread(engine))

    await store.append({**KEY, "subpath": "subagents/agent-1"}, [{"uuid": "x"}])

    assert await store.load(KEY) is None
