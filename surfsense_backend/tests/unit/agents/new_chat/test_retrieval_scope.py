from types import SimpleNamespace

import pytest

from app.agents.chat.retrieval_scope import (
    RetrievalScope,
    denied_retrieval_tools,
    excluded_retrieval_subagents,
)

pytestmark = pytest.mark.unit


def test_documents_scope_removes_public_web_specialists() -> None:
    excluded = excluded_retrieval_subagents(RetrievalScope.DOCUMENTS)
    assert {"google_search", "web_crawler", "youtube"} <= excluded
    assert excluded_retrieval_subagents(RetrievalScope.WEB) == set()
    assert excluded_retrieval_subagents(RetrievalScope.ALL) == set()


def test_documents_scope_denies_connected_app_reads_but_not_writes() -> None:
    tools = [
        SimpleNamespace(
            name="search_messages",
            metadata={"mcp_transport": "http", "hitl": False},
        ),
        SimpleNamespace(
            name="create_issue",
            metadata={"mcp_transport": "http", "hitl": True},
        ),
        SimpleNamespace(
            name="unknown_generic_tool",
            metadata={"mcp_transport": "stdio", "hitl": True, "mcp_is_generic": True},
        ),
    ]

    denied = denied_retrieval_tools(
        RetrievalScope.DOCUMENTS,
        subagent_name="mcp_discovery",
        tools=tools,
    )

    assert "search_messages" in denied
    assert "create_issue" not in denied
    assert "unknown_generic_tool" in denied


def test_web_scope_denies_knowledge_reads_but_not_writes() -> None:
    denied = denied_retrieval_tools(
        RetrievalScope.WEB,
        subagent_name="knowledge_base",
        tools=[],
    )

    assert {"search_knowledge_base", "read_file", "execute_code"} <= denied
    assert "write_file" not in denied
