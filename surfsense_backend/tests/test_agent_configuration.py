"""
Tests for researcher agent configuration.
Tests the Configuration dataclass and SearchMode enum.
"""
import pytest
from dataclasses import fields

from app.agents.researcher.configuration import Configuration, SearchMode


class TestSearchMode:
    """Tests for SearchMode enum."""

    def test_chunks_mode_value(self):
        """Test CHUNKS mode value."""
        assert SearchMode.CHUNKS.value == "CHUNKS"

    def test_documents_mode_value(self):
        """Test DOCUMENTS mode value."""
        assert SearchMode.DOCUMENTS.value == "DOCUMENTS"

    def test_all_modes_are_strings(self):
        """Test all modes have string values."""
        for mode in SearchMode:
            assert isinstance(mode.value, str)

    def test_can_compare_modes(self):
        """Test enum comparison."""
        chunks_mode = SearchMode.CHUNKS
        documents_mode = SearchMode.DOCUMENTS
        assert chunks_mode == SearchMode.CHUNKS
        assert chunks_mode != documents_mode


class TestConfiguration:
    """Tests for Configuration dataclass."""

    def test_create_configuration_with_required_params(self):
        """Test creating configuration with required parameters."""
        config = Configuration(
            user_query="test query",
            connectors_to_search=["TAVILY_API"],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.CHUNKS,
            document_ids_to_add_in_context=[],
        )
        
        assert config.user_query == "test query"
        assert config.connectors_to_search == ["TAVILY_API"]
        assert config.user_id == "user-123"
        assert config.search_space_id == 1
        assert config.search_mode == SearchMode.CHUNKS
        assert config.document_ids_to_add_in_context == []

    def test_create_configuration_with_optional_params(self):
        """Test creating configuration with optional parameters."""
        config = Configuration(
            user_query="test query",
            connectors_to_search=["TAVILY_API"],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.DOCUMENTS,
            document_ids_to_add_in_context=[1, 2, 3],
            language="en",
            top_k=20,
        )
        
        assert config.language == "en"
        assert config.top_k == 20
        assert config.document_ids_to_add_in_context == [1, 2, 3]

    def test_default_language_is_none(self):
        """Test default language is None."""
        config = Configuration(
            user_query="test",
            connectors_to_search=[],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.CHUNKS,
            document_ids_to_add_in_context=[],
        )
        
        assert config.language is None

    def test_default_top_k_is_10(self):
        """Test default top_k is 10."""
        config = Configuration(
            user_query="test",
            connectors_to_search=[],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.CHUNKS,
            document_ids_to_add_in_context=[],
        )
        
        assert config.top_k == 10

    def test_from_runnable_config_with_none(self):
        """Test from_runnable_config with None returns defaults."""
        # This should not raise an error but will fail due to missing required fields
        # We're testing that the method handles None gracefully
        with pytest.raises(TypeError):
            # Missing required fields should raise TypeError
            Configuration.from_runnable_config(None)

    def test_from_runnable_config_with_empty_config(self):
        """Test from_runnable_config with empty config."""
        with pytest.raises(TypeError):
            # Missing required fields should raise TypeError
            Configuration.from_runnable_config({})

    def test_from_runnable_config_with_valid_config(self):
        """Test from_runnable_config with valid config."""
        runnable_config = {
            "configurable": {
                "user_query": "test query",
                "connectors_to_search": ["TAVILY_API"],
                "user_id": "user-123",
                "search_space_id": 1,
                "search_mode": SearchMode.CHUNKS,
                "document_ids_to_add_in_context": [],
                "language": "en",
                "top_k": 15,
            }
        }
        
        config = Configuration.from_runnable_config(runnable_config)
        
        assert config.user_query == "test query"
        assert config.connectors_to_search == ["TAVILY_API"]
        assert config.language == "en"
        assert config.top_k == 15

    def test_from_runnable_config_ignores_unknown_fields(self):
        """Test from_runnable_config ignores unknown fields."""
        runnable_config = {
            "configurable": {
                "user_query": "test query",
                "connectors_to_search": ["TAVILY_API"],
                "user_id": "user-123",
                "search_space_id": 1,
                "search_mode": SearchMode.CHUNKS,
                "document_ids_to_add_in_context": [],
                "unknown_field": "should be ignored",
                "another_unknown": 123,
            }
        }
        
        config = Configuration.from_runnable_config(runnable_config)
        
        assert not hasattr(config, "unknown_field")
        assert not hasattr(config, "another_unknown")

    def test_configuration_has_expected_fields(self):
        """Test Configuration has all expected fields."""
        field_names = {f.name for f in fields(Configuration)}
        
        expected_fields = {
            "user_query",
            "connectors_to_search",
            "user_id",
            "search_space_id",
            "search_mode",
            "document_ids_to_add_in_context",
            "language",
            "top_k",
        }
        
        assert field_names == expected_fields

    def test_configuration_multiple_connectors(self):
        """Test configuration with multiple connectors."""
        config = Configuration(
            user_query="test",
            connectors_to_search=["TAVILY_API", "SLACK_CONNECTOR", "NOTION_CONNECTOR"],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.CHUNKS,
            document_ids_to_add_in_context=[],
        )
        
        assert len(config.connectors_to_search) == 3
        assert "TAVILY_API" in config.connectors_to_search
        assert "SLACK_CONNECTOR" in config.connectors_to_search
        assert "NOTION_CONNECTOR" in config.connectors_to_search

    def test_configuration_with_document_ids(self):
        """Test configuration with document IDs to add to context."""
        config = Configuration(
            user_query="test",
            connectors_to_search=[],
            user_id="user-123",
            search_space_id=1,
            search_mode=SearchMode.CHUNKS,
            document_ids_to_add_in_context=[1, 2, 3, 4, 5],
        )
        
        assert config.document_ids_to_add_in_context == [1, 2, 3, 4, 5]
        assert len(config.document_ids_to_add_in_context) == 5
