"""
Tests for database models and functions.
Tests SQLAlchemy models, enums, and database utility functions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.db import (
    DocumentType,
    LiteLLMProvider,
    SearchSourceConnectorType,
    Permission,
    SearchSpace,
    Document,
    Chunk,
    Chat,
    Podcast,
    LLMConfig,
    SearchSourceConnector,
    SearchSpaceRole,
    SearchSpaceMembership,
    SearchSpaceInvite,
    User,
    LogLevel,
    LogStatus,
    ChatType,
)


class TestDocumentType:
    """Tests for DocumentType enum."""

    def test_all_document_types_are_strings(self):
        """Test all document types have string values."""
        for doc_type in DocumentType:
            assert isinstance(doc_type.value, str)

    def test_extension_type(self):
        """Test EXTENSION document type."""
        assert DocumentType.EXTENSION.value == "EXTENSION"

    def test_file_type(self):
        """Test FILE document type."""
        assert DocumentType.FILE.value == "FILE"

    def test_youtube_video_type(self):
        """Test YOUTUBE_VIDEO document type."""
        assert DocumentType.YOUTUBE_VIDEO.value == "YOUTUBE_VIDEO"

    def test_crawled_url_type(self):
        """Test CRAWLED_URL document type."""
        assert DocumentType.CRAWLED_URL.value == "CRAWLED_URL"

    def test_connector_types_exist(self):
        """Test connector document types exist."""
        connector_types = [
            "SLACK_CONNECTOR",
            "NOTION_CONNECTOR",
            "GITHUB_CONNECTOR",
            "JIRA_CONNECTOR",
            "CONFLUENCE_CONNECTOR",
            "LINEAR_CONNECTOR",
            "DISCORD_CONNECTOR",
        ]
        
        for conn_type in connector_types:
            assert hasattr(DocumentType, conn_type)


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider enum."""

    def test_openai_provider(self):
        """Test OPENAI provider."""
        assert LiteLLMProvider.OPENAI.value == "OPENAI"

    def test_anthropic_provider(self):
        """Test ANTHROPIC provider."""
        assert LiteLLMProvider.ANTHROPIC.value == "ANTHROPIC"

    def test_google_provider(self):
        """Test GOOGLE provider."""
        assert LiteLLMProvider.GOOGLE.value == "GOOGLE"

    def test_ollama_provider(self):
        """Test OLLAMA provider."""
        assert LiteLLMProvider.OLLAMA.value == "OLLAMA"

    def test_all_providers_are_strings(self):
        """Test all providers have string values."""
        for provider in LiteLLMProvider:
            assert isinstance(provider.value, str)


class TestSearchSourceConnectorType:
    """Tests for SearchSourceConnectorType enum."""

    def test_tavily_api(self):
        """Test TAVILY_API connector type."""
        assert SearchSourceConnectorType.TAVILY_API.value == "TAVILY_API"

    def test_searxng_api(self):
        """Test SEARXNG_API connector type."""
        assert SearchSourceConnectorType.SEARXNG_API.value == "SEARXNG_API"

    def test_slack_connector(self):
        """Test SLACK_CONNECTOR connector type."""
        assert SearchSourceConnectorType.SLACK_CONNECTOR.value == "SLACK_CONNECTOR"

    def test_notion_connector(self):
        """Test NOTION_CONNECTOR connector type."""
        assert SearchSourceConnectorType.NOTION_CONNECTOR.value == "NOTION_CONNECTOR"

    def test_all_connector_types_are_strings(self):
        """Test all connector types have string values."""
        for conn_type in SearchSourceConnectorType:
            assert isinstance(conn_type.value, str)


class TestPermission:
    """Tests for Permission enum."""

    def test_full_access_permission(self):
        """Test FULL_ACCESS permission."""
        assert Permission.FULL_ACCESS.value == "*"

    def test_document_permissions(self):
        """Test document permissions exist."""
        doc_permissions = [
            "DOCUMENTS_CREATE",
            "DOCUMENTS_READ",
            "DOCUMENTS_UPDATE",
            "DOCUMENTS_DELETE",
        ]
        
        for perm in doc_permissions:
            assert hasattr(Permission, perm)

    def test_chat_permissions(self):
        """Test chat permissions exist."""
        chat_permissions = [
            "CHATS_CREATE",
            "CHATS_READ",
            "CHATS_UPDATE",
            "CHATS_DELETE",
        ]
        
        for perm in chat_permissions:
            assert hasattr(Permission, perm)

    def test_llm_config_permissions(self):
        """Test LLM config permissions exist."""
        llm_permissions = [
            "LLM_CONFIGS_CREATE",
            "LLM_CONFIGS_READ",
            "LLM_CONFIGS_UPDATE",
            "LLM_CONFIGS_DELETE",
        ]
        
        for perm in llm_permissions:
            assert hasattr(Permission, perm)

    def test_settings_permissions(self):
        """Test settings permissions exist."""
        settings_permissions = [
            "SETTINGS_VIEW",
            "SETTINGS_UPDATE",
            "SETTINGS_DELETE",
        ]
        
        for perm in settings_permissions:
            assert hasattr(Permission, perm)


class TestSearchSpaceModel:
    """Tests for SearchSpace model."""

    def test_search_space_has_required_fields(self):
        """Test SearchSpace has required fields."""
        # Check that the model has expected columns
        assert hasattr(SearchSpace, 'id')
        assert hasattr(SearchSpace, 'name')
        assert hasattr(SearchSpace, 'user_id')
        assert hasattr(SearchSpace, 'created_at')


class TestDocumentModel:
    """Tests for Document model."""

    def test_document_has_required_fields(self):
        """Test Document has required fields."""
        assert hasattr(Document, 'id')
        assert hasattr(Document, 'title')
        assert hasattr(Document, 'document_type')
        assert hasattr(Document, 'content')
        assert hasattr(Document, 'search_space_id')

    def test_document_has_chunks_relationship(self):
        """Test Document has chunks relationship."""
        assert hasattr(Document, 'chunks')


class TestChunkModel:
    """Tests for Chunk model."""

    def test_chunk_has_required_fields(self):
        """Test Chunk has required fields."""
        assert hasattr(Chunk, 'id')
        assert hasattr(Chunk, 'content')
        assert hasattr(Chunk, 'document_id')

    def test_chunk_has_embedding_field(self):
        """Test Chunk has embedding field."""
        assert hasattr(Chunk, 'embedding')


class TestChatModel:
    """Tests for Chat model."""

    def test_chat_has_required_fields(self):
        """Test Chat has required fields."""
        assert hasattr(Chat, 'id')
        assert hasattr(Chat, 'title')
        assert hasattr(Chat, 'search_space_id')


class TestChatType:
    """Tests for ChatType enum."""

    def test_chat_type_values(self):
        """Test ChatType values."""
        assert hasattr(ChatType, 'QNA')


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self):
        """Test LogLevel values exist."""
        assert hasattr(LogLevel, 'INFO')
        assert hasattr(LogLevel, 'WARNING')
        assert hasattr(LogLevel, 'ERROR')


class TestLogStatus:
    """Tests for LogStatus enum."""

    def test_log_status_values(self):
        """Test LogStatus values exist."""
        assert hasattr(LogStatus, 'IN_PROGRESS')
        assert hasattr(LogStatus, 'SUCCESS')
        assert hasattr(LogStatus, 'FAILED')
        assert LogStatus.IN_PROGRESS.value == "IN_PROGRESS"


class TestLLMConfigModel:
    """Tests for LLMConfig model."""

    def test_llm_config_has_required_fields(self):
        """Test LLMConfig has required fields."""
        assert hasattr(LLMConfig, 'id')
        assert hasattr(LLMConfig, 'name')
        assert hasattr(LLMConfig, 'provider')
        assert hasattr(LLMConfig, 'model_name')
        assert hasattr(LLMConfig, 'api_key')
        assert hasattr(LLMConfig, 'search_space_id')


class TestSearchSourceConnectorModel:
    """Tests for SearchSourceConnector model."""

    def test_connector_has_required_fields(self):
        """Test SearchSourceConnector has required fields."""
        assert hasattr(SearchSourceConnector, 'id')
        assert hasattr(SearchSourceConnector, 'connector_type')
        assert hasattr(SearchSourceConnector, 'config')
        assert hasattr(SearchSourceConnector, 'search_space_id')


class TestRBACModels:
    """Tests for RBAC models."""

    def test_search_space_role_has_required_fields(self):
        """Test SearchSpaceRole has required fields."""
        assert hasattr(SearchSpaceRole, 'id')
        assert hasattr(SearchSpaceRole, 'name')
        assert hasattr(SearchSpaceRole, 'permissions')
        assert hasattr(SearchSpaceRole, 'search_space_id')

    def test_search_space_membership_has_required_fields(self):
        """Test SearchSpaceMembership has required fields."""
        assert hasattr(SearchSpaceMembership, 'id')
        assert hasattr(SearchSpaceMembership, 'user_id')
        assert hasattr(SearchSpaceMembership, 'search_space_id')
        assert hasattr(SearchSpaceMembership, 'role_id')
        assert hasattr(SearchSpaceMembership, 'is_owner')

    def test_search_space_invite_has_required_fields(self):
        """Test SearchSpaceInvite has required fields."""
        assert hasattr(SearchSpaceInvite, 'id')
        assert hasattr(SearchSpaceInvite, 'invite_code')
        assert hasattr(SearchSpaceInvite, 'search_space_id')
        assert hasattr(SearchSpaceInvite, 'role_id')


class TestUserModel:
    """Tests for User model."""

    def test_user_has_required_fields(self):
        """Test User has required fields."""
        assert hasattr(User, 'id')
        assert hasattr(User, 'email')

    def test_user_has_page_limit_fields(self):
        """Test User has page limit fields."""
        assert hasattr(User, 'pages_used')
        assert hasattr(User, 'pages_limit')


class TestPodcastModel:
    """Tests for Podcast model."""

    def test_podcast_has_required_fields(self):
        """Test Podcast has required fields."""
        assert hasattr(Podcast, 'id')
        assert hasattr(Podcast, 'title')
        assert hasattr(Podcast, 'search_space_id')
