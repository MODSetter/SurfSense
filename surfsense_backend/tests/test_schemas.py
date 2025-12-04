"""
Tests for Pydantic schema models.

This module tests schema validation, serialization, and deserialization
for all schema models used in the application.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db import ChatType, DocumentType, LiteLLMProvider
from app.schemas.base import IDModel, TimestampModel
from app.schemas.chats import (
    AISDKChatRequest,
    ChatBase,
    ChatCreate,
    ChatRead,
    ChatReadWithoutMessages,
    ChatUpdate,
    ClientAttachment,
    ToolInvocation,
)
from app.schemas.chunks import ChunkBase, ChunkCreate, ChunkRead, ChunkUpdate
from app.schemas.documents import (
    DocumentBase,
    DocumentRead,
    DocumentsCreate,
    DocumentUpdate,
    DocumentWithChunksRead,
    ExtensionDocumentContent,
    ExtensionDocumentMetadata,
    PaginatedResponse,
)
from app.schemas.llm_config import (
    LLMConfigBase,
    LLMConfigCreate,
    LLMConfigRead,
    LLMConfigUpdate,
)
from app.schemas.search_space import (
    SearchSpaceBase,
    SearchSpaceCreate,
    SearchSpaceRead,
    SearchSpaceUpdate,
    SearchSpaceWithStats,
)


class TestBaseSchemas:
    """Tests for base schema models."""

    def test_timestamp_model(self):
        """Test TimestampModel with valid datetime."""
        now = datetime.now(timezone.utc)
        model = TimestampModel(created_at=now)
        assert model.created_at == now

    def test_id_model(self):
        """Test IDModel with valid ID."""
        model = IDModel(id=1)
        assert model.id == 1

    def test_id_model_with_zero(self):
        """Test IDModel accepts zero."""
        model = IDModel(id=0)
        assert model.id == 0


class TestChatSchemas:
    """Tests for chat-related schema models."""

    def test_chat_base_valid(self):
        """Test ChatBase with valid data."""
        chat = ChatBase(
            type=ChatType.QNA,
            title="Test Chat",
            messages=[{"role": "user", "content": "Hello"}],
            search_space_id=1,
        )
        assert chat.type == ChatType.QNA
        assert chat.title == "Test Chat"
        assert chat.search_space_id == 1
        assert chat.state_version == 1

    def test_chat_base_with_connectors(self):
        """Test ChatBase with initial connectors."""
        chat = ChatBase(
            type=ChatType.QNA,
            title="Test Chat",
            initial_connectors=["slack", "notion"],
            messages=[],
            search_space_id=1,
        )
        assert chat.initial_connectors == ["slack", "notion"]

    def test_chat_base_default_state_version(self):
        """Test ChatBase default state_version."""
        chat = ChatBase(
            type=ChatType.QNA,
            title="Test Chat",
            messages=[],
            search_space_id=1,
        )
        assert chat.state_version == 1

    def test_chat_create(self):
        """Test ChatCreate schema."""
        chat = ChatCreate(
            type=ChatType.QNA,
            title="New Chat",
            messages=[{"role": "user", "content": "Test"}],
            search_space_id=1,
        )
        assert chat.title == "New Chat"

    def test_chat_update(self):
        """Test ChatUpdate schema."""
        chat = ChatUpdate(
            type=ChatType.QNA,
            title="Updated Chat",
            messages=[{"role": "user", "content": "Updated"}],
            search_space_id=1,
            state_version=2,
        )
        assert chat.state_version == 2

    def test_chat_read(self):
        """Test ChatRead schema."""
        now = datetime.now(timezone.utc)
        chat = ChatRead(
            id=1,
            type=ChatType.QNA,
            title="Read Chat",
            messages=[],
            search_space_id=1,
            created_at=now,
        )
        assert chat.id == 1
        assert chat.created_at == now

    def test_chat_read_without_messages(self):
        """Test ChatReadWithoutMessages schema."""
        now = datetime.now(timezone.utc)
        chat = ChatReadWithoutMessages(
            id=1,
            type=ChatType.QNA,
            title="Chat Without Messages",
            search_space_id=1,
            created_at=now,
        )
        assert chat.id == 1
        assert not hasattr(chat, "messages") or "messages" not in chat.model_fields

    def test_client_attachment(self):
        """Test ClientAttachment schema."""
        attachment = ClientAttachment(
            name="test.pdf",
            content_type="application/pdf",
            url="https://example.com/test.pdf",
        )
        assert attachment.name == "test.pdf"
        assert attachment.content_type == "application/pdf"

    def test_tool_invocation(self):
        """Test ToolInvocation schema."""
        tool = ToolInvocation(
            tool_call_id="tc_123",
            tool_name="search",
            args={"query": "test"},
            result={"results": []},
        )
        assert tool.tool_call_id == "tc_123"
        assert tool.tool_name == "search"

    def test_aisdk_chat_request(self):
        """Test AISDKChatRequest schema."""
        request = AISDKChatRequest(
            messages=[{"role": "user", "content": "Hello"}],
            data={"search_space_id": 1},
        )
        assert len(request.messages) == 1
        assert request.data["search_space_id"] == 1

    def test_aisdk_chat_request_no_data(self):
        """Test AISDKChatRequest without data."""
        request = AISDKChatRequest(messages=[{"role": "user", "content": "Hello"}])
        assert request.data is None


class TestChunkSchemas:
    """Tests for chunk-related schema models."""

    def test_chunk_base(self):
        """Test ChunkBase schema."""
        chunk = ChunkBase(content="Test content", document_id=1)
        assert chunk.content == "Test content"
        assert chunk.document_id == 1

    def test_chunk_create(self):
        """Test ChunkCreate schema."""
        chunk = ChunkCreate(content="New chunk content", document_id=1)
        assert chunk.content == "New chunk content"

    def test_chunk_update(self):
        """Test ChunkUpdate schema."""
        chunk = ChunkUpdate(content="Updated content", document_id=1)
        assert chunk.content == "Updated content"

    def test_chunk_read(self):
        """Test ChunkRead schema."""
        now = datetime.now(timezone.utc)
        chunk = ChunkRead(
            id=1,
            content="Read chunk",
            document_id=1,
            created_at=now,
        )
        assert chunk.id == 1
        assert chunk.created_at == now


class TestDocumentSchemas:
    """Tests for document-related schema models."""

    def test_extension_document_metadata(self):
        """Test ExtensionDocumentMetadata schema."""
        metadata = ExtensionDocumentMetadata(
            BrowsingSessionId="session123",
            VisitedWebPageURL="https://example.com",
            VisitedWebPageTitle="Example Page",
            VisitedWebPageDateWithTimeInISOString="2024-01-01T00:00:00Z",
            VisitedWebPageReffererURL="https://google.com",
            VisitedWebPageVisitDurationInMilliseconds="5000",
        )
        assert metadata.BrowsingSessionId == "session123"
        assert metadata.VisitedWebPageURL == "https://example.com"

    def test_extension_document_content(self):
        """Test ExtensionDocumentContent schema."""
        metadata = ExtensionDocumentMetadata(
            BrowsingSessionId="session123",
            VisitedWebPageURL="https://example.com",
            VisitedWebPageTitle="Example Page",
            VisitedWebPageDateWithTimeInISOString="2024-01-01T00:00:00Z",
            VisitedWebPageReffererURL="https://google.com",
            VisitedWebPageVisitDurationInMilliseconds="5000",
        )
        content = ExtensionDocumentContent(
            metadata=metadata,
            pageContent="This is the page content",
        )
        assert content.pageContent == "This is the page content"
        assert content.metadata.VisitedWebPageTitle == "Example Page"

    def test_document_base_with_string_content(self):
        """Test DocumentBase with string content."""
        doc = DocumentBase(
            document_type=DocumentType.FILE,
            content="This is document content",
            search_space_id=1,
        )
        assert doc.content == "This is document content"

    def test_document_base_with_list_content(self):
        """Test DocumentBase with list content."""
        doc = DocumentBase(
            document_type=DocumentType.FILE,
            content=["Part 1", "Part 2"],
            search_space_id=1,
        )
        assert len(doc.content) == 2

    def test_documents_create(self):
        """Test DocumentsCreate schema."""
        doc = DocumentsCreate(
            document_type=DocumentType.CRAWLED_URL,
            content="Crawled content",
            search_space_id=1,
        )
        assert doc.document_type == DocumentType.CRAWLED_URL

    def test_document_update(self):
        """Test DocumentUpdate schema."""
        doc = DocumentUpdate(
            document_type=DocumentType.FILE,
            content="Updated content",
            search_space_id=1,
        )
        assert doc.content == "Updated content"

    def test_document_read(self):
        """Test DocumentRead schema."""
        now = datetime.now(timezone.utc)
        doc = DocumentRead(
            id=1,
            title="Test Document",
            document_type=DocumentType.FILE,
            document_metadata={"key": "value"},
            content="Content",
            created_at=now,
            search_space_id=1,
        )
        assert doc.id == 1
        assert doc.title == "Test Document"
        assert doc.document_metadata["key"] == "value"

    def test_document_with_chunks_read(self):
        """Test DocumentWithChunksRead schema."""
        now = datetime.now(timezone.utc)
        doc = DocumentWithChunksRead(
            id=1,
            title="Test Document",
            document_type=DocumentType.FILE,
            document_metadata={},
            content="Content",
            created_at=now,
            search_space_id=1,
            chunks=[
                ChunkRead(id=1, content="Chunk 1", document_id=1, created_at=now),
                ChunkRead(id=2, content="Chunk 2", document_id=1, created_at=now),
            ],
        )
        assert len(doc.chunks) == 2

    def test_paginated_response(self):
        """Test PaginatedResponse schema."""
        response = PaginatedResponse[dict](
            items=[{"id": 1}, {"id": 2}],
            total=10,
        )
        assert len(response.items) == 2
        assert response.total == 10


class TestLLMConfigSchemas:
    """Tests for LLM config schema models."""

    def test_llm_config_base(self):
        """Test LLMConfigBase schema."""
        config = LLMConfigBase(
            name="GPT-4 Config",
            provider=LiteLLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="sk-test123",
        )
        assert config.name == "GPT-4 Config"
        assert config.provider == LiteLLMProvider.OPENAI
        assert config.language == "English"  # Default value

    def test_llm_config_base_with_custom_provider(self):
        """Test LLMConfigBase with custom provider."""
        config = LLMConfigBase(
            name="Custom LLM",
            provider=LiteLLMProvider.CUSTOM,
            custom_provider="my-provider",
            model_name="my-model",
            api_key="test-key",
            api_base="https://my-api.com/v1",
        )
        assert config.custom_provider == "my-provider"
        assert config.api_base == "https://my-api.com/v1"

    def test_llm_config_base_with_litellm_params(self):
        """Test LLMConfigBase with litellm params."""
        config = LLMConfigBase(
            name="Config with Params",
            provider=LiteLLMProvider.ANTHROPIC,
            model_name="claude-3-opus",
            api_key="test-key",
            litellm_params={"temperature": 0.7, "max_tokens": 1000},
        )
        assert config.litellm_params["temperature"] == 0.7

    def test_llm_config_create(self):
        """Test LLMConfigCreate schema."""
        config = LLMConfigCreate(
            name="New Config",
            provider=LiteLLMProvider.GROQ,
            model_name="llama-3",
            api_key="gsk-test",
            search_space_id=1,
        )
        assert config.search_space_id == 1

    def test_llm_config_update_partial(self):
        """Test LLMConfigUpdate with partial data."""
        update = LLMConfigUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.provider is None
        assert update.model_name is None

    def test_llm_config_update_full(self):
        """Test LLMConfigUpdate with full data."""
        update = LLMConfigUpdate(
            name="Full Update",
            provider=LiteLLMProvider.MISTRAL,
            model_name="mistral-large",
            api_key="new-key",
            language="French",
        )
        assert update.language == "French"

    def test_llm_config_read(self):
        """Test LLMConfigRead schema."""
        now = datetime.now(timezone.utc)
        config = LLMConfigRead(
            id=1,
            name="Read Config",
            provider=LiteLLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="sk-test",
            created_at=now,
            search_space_id=1,
        )
        assert config.id == 1
        assert config.created_at == now

    def test_llm_config_read_global(self):
        """Test LLMConfigRead for global config (no search_space_id)."""
        config = LLMConfigRead(
            id=-1,
            name="Global Config",
            provider=LiteLLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="sk-global",
            created_at=None,
            search_space_id=None,
        )
        assert config.id == -1
        assert config.search_space_id is None


class TestSearchSpaceSchemas:
    """Tests for search space schema models."""

    def test_search_space_base(self):
        """Test SearchSpaceBase schema."""
        space = SearchSpaceBase(name="My Search Space")
        assert space.name == "My Search Space"
        assert space.description is None

    def test_search_space_base_with_description(self):
        """Test SearchSpaceBase with description."""
        space = SearchSpaceBase(
            name="My Search Space",
            description="A space for searching",
        )
        assert space.description == "A space for searching"

    def test_search_space_create_defaults(self):
        """Test SearchSpaceCreate with default values."""
        space = SearchSpaceCreate(name="New Space")
        assert space.citations_enabled is True
        assert space.qna_custom_instructions is None

    def test_search_space_create_custom(self):
        """Test SearchSpaceCreate with custom values."""
        space = SearchSpaceCreate(
            name="Custom Space",
            description="Custom description",
            citations_enabled=False,
            qna_custom_instructions="Be concise",
        )
        assert space.citations_enabled is False
        assert space.qna_custom_instructions == "Be concise"

    def test_search_space_update_partial(self):
        """Test SearchSpaceUpdate with partial data."""
        update = SearchSpaceUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.description is None
        assert update.citations_enabled is None

    def test_search_space_update_full(self):
        """Test SearchSpaceUpdate with all fields."""
        update = SearchSpaceUpdate(
            name="Full Update",
            description="New description",
            citations_enabled=True,
            qna_custom_instructions="New instructions",
        )
        assert update.qna_custom_instructions == "New instructions"

    def test_search_space_read(self):
        """Test SearchSpaceRead schema."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        space = SearchSpaceRead(
            id=1,
            name="Read Space",
            description="Description",
            created_at=now,
            user_id=user_id,
            citations_enabled=True,
            qna_custom_instructions=None,
        )
        assert space.id == 1
        assert space.user_id == user_id

    def test_search_space_with_stats(self):
        """Test SearchSpaceWithStats schema."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        space = SearchSpaceWithStats(
            id=1,
            name="Space with Stats",
            created_at=now,
            user_id=user_id,
            citations_enabled=True,
            member_count=5,
            is_owner=True,
        )
        assert space.member_count == 5
        assert space.is_owner is True

    def test_search_space_with_stats_defaults(self):
        """Test SearchSpaceWithStats default values."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        space = SearchSpaceWithStats(
            id=1,
            name="Default Stats Space",
            created_at=now,
            user_id=user_id,
            citations_enabled=True,
        )
        assert space.member_count == 1
        assert space.is_owner is False


class TestSchemaValidation:
    """Tests for schema validation errors."""

    def test_chat_base_missing_required(self):
        """Test ChatBase raises error for missing required fields."""
        with pytest.raises(ValidationError):
            ChatBase(type=ChatType.QNA, title="Test")  # Missing messages and search_space_id

    def test_llm_config_name_too_long(self):
        """Test LLMConfigBase validates name length."""
        with pytest.raises(ValidationError):
            LLMConfigBase(
                name="x" * 101,  # Exceeds max_length of 100
                provider=LiteLLMProvider.OPENAI,
                model_name="gpt-4",
                api_key="test",
            )

    def test_llm_config_model_name_too_long(self):
        """Test LLMConfigBase validates model_name length."""
        with pytest.raises(ValidationError):
            LLMConfigBase(
                name="Valid Name",
                provider=LiteLLMProvider.OPENAI,
                model_name="x" * 101,  # Exceeds max_length of 100
                api_key="test",
            )

    def test_document_read_missing_required(self):
        """Test DocumentRead raises error for missing required fields."""
        with pytest.raises(ValidationError):
            DocumentRead(
                id=1,
                title="Test",
                # Missing document_type, document_metadata, content, created_at, search_space_id
            )
