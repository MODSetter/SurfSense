import pytest
from pydantic import ValidationError

from app.agents.chat.retrieval_scope import RetrievalScope
from app.schemas.new_chat import NewChatRequest

pytestmark = pytest.mark.unit


def test_request_rejects_scope_and_mention_conflicts() -> None:
    with pytest.raises(ValidationError, match="connected-app mentions"):
        NewChatRequest(
            chat_id=1,
            workspace_id=1,
            user_query="Use this connector",
            retrieval_scope=RetrievalScope.DOCUMENTS,
            mentioned_connector_ids=[7],
        )

    with pytest.raises(ValidationError, match="document, folder, or thread mentions"):
        NewChatRequest(
            chat_id=1,
            workspace_id=1,
            user_query="Use this document",
            retrieval_scope=RetrievalScope.WEB,
            mentioned_document_ids=[7],
        )
