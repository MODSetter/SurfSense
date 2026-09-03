"""Chat: roles are a closed set because prompt assembly branches on them."""

import pytest
from sqlalchemy import Engine, exc, insert

from modules.chat.models import ChatMessage, ChatThread
from modules.workspaces.models import Workspace


def test_chat_messages_reject_an_unknown_role(engine: Engine) -> None:
    """Roles drive prompt assembly, so an unknown one must never reach the db."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        connection.execute(insert(ChatThread).values(id=1, workspace_id=1))

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(ChatMessage).values(chat_thread_id=1, role="root", content={})
        )
