"""
Tests for the validators module.
"""

import pytest
from fastapi import HTTPException

from app.utils.validators import (
    validate_connectors,
    validate_document_ids,
    validate_email,
    validate_messages,
    validate_research_mode,
    validate_search_mode,
    validate_search_space_id,
    validate_top_k,
    validate_url,
    validate_uuid,
)


class TestValidateSearchSpaceId:
    """Tests for validate_search_space_id function."""

    def test_valid_integer(self):
        """Test valid integer input."""
        assert validate_search_space_id(1) == 1
        assert validate_search_space_id(100) == 100
        assert validate_search_space_id(999999) == 999999

    def test_valid_string(self):
        """Test valid string input."""
        assert validate_search_space_id("1") == 1
        assert validate_search_space_id("100") == 100
        assert validate_search_space_id(" 50 ") == 50  # Trimmed

    def test_none_raises_error(self):
        """Test that None raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id(None)
        assert exc_info.value.status_code == 400
        assert "required" in exc_info.value.detail

    def test_zero_raises_error(self):
        """Test that zero raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id(0)
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_negative_raises_error(self):
        """Test that negative values raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id(-1)
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_boolean_raises_error(self):
        """Test that boolean raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id(True)
        assert exc_info.value.status_code == 400
        assert "boolean" in exc_info.value.detail

    def test_empty_string_raises_error(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id("")
        assert exc_info.value.status_code == 400

    def test_invalid_string_raises_error(self):
        """Test that invalid string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id("abc")
        assert exc_info.value.status_code == 400

    def test_float_raises_error(self):
        """Test that float raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_space_id(1.5)
        assert exc_info.value.status_code == 400


class TestValidateDocumentIds:
    """Tests for validate_document_ids function."""

    def test_none_returns_empty_list(self):
        """Test that None returns empty list."""
        assert validate_document_ids(None) == []

    def test_empty_list_returns_empty_list(self):
        """Test that empty list returns empty list."""
        assert validate_document_ids([]) == []

    def test_valid_integer_list(self):
        """Test valid integer list."""
        assert validate_document_ids([1, 2, 3]) == [1, 2, 3]

    def test_valid_string_list(self):
        """Test valid string list."""
        assert validate_document_ids(["1", "2", "3"]) == [1, 2, 3]

    def test_mixed_valid_types(self):
        """Test mixed valid types."""
        assert validate_document_ids([1, "2", 3]) == [1, 2, 3]

    def test_not_list_raises_error(self):
        """Test that non-list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_document_ids("not a list")
        assert exc_info.value.status_code == 400
        assert "must be a list" in exc_info.value.detail

    def test_negative_id_raises_error(self):
        """Test that negative ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_document_ids([1, -2, 3])
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_zero_id_raises_error(self):
        """Test that zero ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_document_ids([0])
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_boolean_in_list_raises_error(self):
        """Test that boolean in list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_document_ids([1, True, 3])
        assert exc_info.value.status_code == 400
        assert "boolean" in exc_info.value.detail


class TestValidateConnectors:
    """Tests for validate_connectors function."""

    def test_none_returns_empty_list(self):
        """Test that None returns empty list."""
        assert validate_connectors(None) == []

    def test_empty_list_returns_empty_list(self):
        """Test that empty list returns empty list."""
        assert validate_connectors([]) == []

    def test_valid_connectors(self):
        """Test valid connector names."""
        assert validate_connectors(["slack", "github"]) == ["slack", "github"]

    def test_connector_with_underscore(self):
        """Test connector names with underscores."""
        assert validate_connectors(["google_calendar"]) == ["google_calendar"]

    def test_connector_with_hyphen(self):
        """Test connector names with hyphens."""
        assert validate_connectors(["google-calendar"]) == ["google-calendar"]

    def test_not_list_raises_error(self):
        """Test that non-list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_connectors("not a list")
        assert exc_info.value.status_code == 400
        assert "must be a list" in exc_info.value.detail

    def test_non_string_in_list_raises_error(self):
        """Test that non-string in list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_connectors(["slack", 123])
        assert exc_info.value.status_code == 400
        assert "must be a string" in exc_info.value.detail

    def test_empty_string_raises_error(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_connectors(["slack", ""])
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_invalid_characters_raises_error(self):
        """Test that invalid characters raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_connectors(["slack@connector"])
        assert exc_info.value.status_code == 400
        assert "invalid characters" in exc_info.value.detail


class TestValidateResearchMode:
    """Tests for validate_research_mode function."""

    def test_none_returns_default(self):
        """Test that None returns default value."""
        assert validate_research_mode(None) == "QNA"

    def test_valid_mode(self):
        """Test valid mode."""
        assert validate_research_mode("QNA") == "QNA"
        assert validate_research_mode("qna") == "QNA"  # Case insensitive

    def test_non_string_raises_error(self):
        """Test that non-string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_research_mode(123)
        assert exc_info.value.status_code == 400
        assert "must be a string" in exc_info.value.detail

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_research_mode("INVALID")
        assert exc_info.value.status_code == 400
        assert "must be one of" in exc_info.value.detail


class TestValidateSearchMode:
    """Tests for validate_search_mode function."""

    def test_none_returns_default(self):
        """Test that None returns default value."""
        assert validate_search_mode(None) == "CHUNKS"

    def test_valid_modes(self):
        """Test valid modes."""
        assert validate_search_mode("CHUNKS") == "CHUNKS"
        assert validate_search_mode("DOCUMENTS") == "DOCUMENTS"
        assert validate_search_mode("chunks") == "CHUNKS"  # Case insensitive

    def test_non_string_raises_error(self):
        """Test that non-string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_mode(123)
        assert exc_info.value.status_code == 400
        assert "must be a string" in exc_info.value.detail

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_search_mode("INVALID")
        assert exc_info.value.status_code == 400
        assert "must be one of" in exc_info.value.detail


class TestValidateTopK:
    """Tests for validate_top_k function."""

    def test_none_returns_default(self):
        """Test that None returns default value."""
        assert validate_top_k(None) == 10

    def test_valid_integer(self):
        """Test valid integer input."""
        assert validate_top_k(1) == 1
        assert validate_top_k(50) == 50
        assert validate_top_k(100) == 100

    def test_valid_string(self):
        """Test valid string input."""
        assert validate_top_k("5") == 5
        assert validate_top_k(" 10 ") == 10

    def test_zero_raises_error(self):
        """Test that zero raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_top_k(0)
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_negative_raises_error(self):
        """Test that negative values raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_top_k(-1)
        assert exc_info.value.status_code == 400
        assert "positive" in exc_info.value.detail

    def test_exceeds_max_raises_error(self):
        """Test that values over 100 raise HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_top_k(101)
        assert exc_info.value.status_code == 400
        assert "exceed 100" in exc_info.value.detail

    def test_boolean_raises_error(self):
        """Test that boolean raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_top_k(True)
        assert exc_info.value.status_code == 400
        assert "boolean" in exc_info.value.detail


class TestValidateMessages:
    """Tests for validate_messages function."""

    def test_valid_messages(self):
        """Test valid messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = validate_messages(messages)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_trims_content(self):
        """Test that content is trimmed."""
        messages = [{"role": "user", "content": "  Hello  "}]
        result = validate_messages(messages)
        assert result[0]["content"] == "Hello"

    def test_system_message_valid(self):
        """Test that system messages are valid."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = validate_messages(messages)
        assert result[0]["role"] == "system"

    def test_not_list_raises_error(self):
        """Test that non-list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages("not a list")
        assert exc_info.value.status_code == 400
        assert "must be a list" in exc_info.value.detail

    def test_empty_list_raises_error(self):
        """Test that empty list raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages([])
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    def test_missing_role_raises_error(self):
        """Test that missing role raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages([{"content": "Hello"}])
        assert exc_info.value.status_code == 400
        assert "role" in exc_info.value.detail

    def test_missing_content_raises_error(self):
        """Test that missing content raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages([{"role": "user"}])
        assert exc_info.value.status_code == 400
        assert "content" in exc_info.value.detail

    def test_invalid_role_raises_error(self):
        """Test that invalid role raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages([{"role": "invalid", "content": "Hello"}])
        assert exc_info.value.status_code == 400
        assert "role" in exc_info.value.detail

    def test_empty_content_raises_error(self):
        """Test that empty content raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_messages([{"role": "user", "content": "   "}])
        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_email(self):
        """Test valid email addresses."""
        assert validate_email("test@example.com") == "test@example.com"
        assert validate_email("user.name@domain.co.uk") == "user.name@domain.co.uk"

    def test_trims_whitespace(self):
        """Test that whitespace is trimmed."""
        assert validate_email("  test@example.com  ") == "test@example.com"

    def test_empty_raises_error(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_email("")
        assert exc_info.value.status_code == 400

    def test_invalid_format_raises_error(self):
        """Test that invalid format raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_email("not-an-email")
        assert exc_info.value.status_code == 400
        assert "Invalid email" in exc_info.value.detail


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_url(self):
        """Test valid URLs."""
        assert validate_url("https://example.com") == "https://example.com"
        assert (
            validate_url("http://sub.domain.com/path")
            == "http://sub.domain.com/path"
        )

    def test_trims_whitespace(self):
        """Test that whitespace is trimmed."""
        assert validate_url("  https://example.com  ") == "https://example.com"

    def test_empty_raises_error(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_url("")
        assert exc_info.value.status_code == 400

    def test_invalid_format_raises_error(self):
        """Test that invalid format raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_url("not-a-url")
        assert exc_info.value.status_code == 400
        assert "Invalid URL" in exc_info.value.detail


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_valid_uuid(self):
        """Test valid UUIDs."""
        uuid_str = "123e4567-e89b-12d3-a456-426614174000"
        assert validate_uuid(uuid_str) == uuid_str

    def test_trims_whitespace(self):
        """Test that whitespace is trimmed."""
        uuid_str = "  123e4567-e89b-12d3-a456-426614174000  "
        assert validate_uuid(uuid_str) == "123e4567-e89b-12d3-a456-426614174000"

    def test_empty_raises_error(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("")
        assert exc_info.value.status_code == 400

    def test_invalid_format_raises_error(self):
        """Test that invalid format raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("not-a-uuid")
        assert exc_info.value.status_code == 400
        assert "Invalid UUID" in exc_info.value.detail
