import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

os.environ["EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"
os.environ["RERANKERS_MODEL_NAME"] = "flashrank"
os.environ["RERANKERS_MODEL_TYPE"] = "flashrank"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from surfsense_backend.app.agents.alison.graph import graph as alison_graph
from surfsense_backend.app.agents.alison.state import AlisonState

@pytest.mark.asyncio
@patch('surfsense_backend.app.services.llm_service.get_user_fast_llm')
@patch('surfsense_backend.app.retriever.alison_knowledge_retriever.AlisonKnowledgeRetriever')
async def test_alison_graph_success_path(mock_retriever_cls, mock_llm_service):
    # Mock the LLM
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="projector not working"))
    mock_llm_service.return_value = mock_llm

    # Mock the retriever
    mock_retriever_instance = mock_retriever_cls.return_value
    mock_retriever_instance.hybrid_search.return_value = [{"content": "Check the power cable."}]

    # Mock the db session
    mock_session = AsyncMock()

    # Mock the streaming service
    mock_streaming_service = MagicMock()

    config = {
        "configurable": {
            "user_id": "test_user",
            "user_role": "professor",
        }
    }
    initial_state = AlisonState(
        user_query="My projector is not working.",
        db_session=mock_session,
        streaming_service=mock_streaming_service,
        chat_history=[],
        identified_problem=None,
        troubleshooting_steps=None,
        visual_aids=None,
        escalation_required=False,
        final_response=None,
    )

    # Astream the graph to get the final state
    final_chunk = None
    async for chunk in alison_graph.astream(initial_state, config=config):
        final_chunk = chunk

    assert final_chunk is not None
    last_state = final_chunk[list(final_chunk.keys())[-1]]
    assert "Check the power cable" in last_state["final_response"]

@pytest.mark.asyncio
@patch('surfsense_backend.app.services.llm_service.get_user_fast_llm')
@patch('surfsense_backend.app.retriever.alison_knowledge_retriever.AlisonKnowledgeRetriever')
async def test_alison_graph_escalation_path(mock_retriever_cls, mock_llm_service):
    # Mock the LLM
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="I am unable to resolve this issue. Please contact IT support."))
    mock_llm_service.return_value = mock_llm

    # Mock the retriever to return no documents
    mock_retriever_instance = mock_retriever_cls.return_value
    mock_retriever_instance.hybrid_search.return_value = []

    # Mock the db session
    mock_session = AsyncMock()

    # Mock the streaming service
    mock_streaming_service = MagicMock()

    config = {
        "configurable": {
            "user_id": "test_user",
            "user_role": "professor",
        }
    }
    initial_state = AlisonState(
        user_query="My projector is not working.",
        db_session=mock_session,
        streaming_service=mock_streaming_service,
        chat_history=[],
        identified_problem=None,
        troubleshooting_steps=None,
        visual_aids=None,
        escalation_required=False,
        final_response=None,
    )

    # Astream the graph to get the final state
    final_chunk = None
    async for chunk in alison_graph.astream(initial_state, config=config):
        final_chunk = chunk

    assert final_chunk is not None
    last_state = final_chunk[list(final_chunk.keys())[-1]]
    assert "Please contact IT support" in last_state["final_response"]

def test_alison_imports():
    from surfsense_backend.app.retriever.alison_knowledge_retriever import AlisonKnowledgeRetriever
    mock_session = MagicMock()
    retriever = AlisonKnowledgeRetriever(mock_session)
    assert retriever is not None
