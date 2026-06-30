"""Tests for the validators module."""

import pytest
from fastapi import HTTPException

from app.utils.validators import (
    validate_connector_config,
    validate_connectors,
    validate_document_ids,
    validate_email,
    validate_messages,
    validate_research_mode,
    validate_search_mode,
    validate_workspace_id,
    validate_top_k,
    validate_url,
    validate_uuid,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# IDs and Pagination Validators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valid_input, expected",
    [
        (1, 1),
        (42, 42),
        ("1", 1),
        (" 42 ", 42),
    ],
)
def test_validate_workspace_id_valid(valid_input, expected):
    assert validate_workspace_id(valid_input) == expected


@pytest.mark.parametrize(
    "invalid_input",
    [
        None,
        True,
        False,
        0,
        -1,
        "",
        "   ",
        "abc",
        "1.5",
        "0",
        "-5",
    ],
)
def test_validate_workspace_id_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_workspace_id(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_document_ids_valid():
    assert validate_document_ids(None) == []
    assert validate_document_ids([1, 2, 3]) == [1, 2, 3]
    assert validate_document_ids(["1", " 2 ", 3]) == [1, 2, 3]


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a list",
        123,
        [True],
        [0],
        [-1],
        [""],
        ["   "],
        ["abc"],
        [1, "abc"],
    ],
)
def test_validate_document_ids_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_document_ids(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_top_k_valid():
    assert validate_top_k(None) == 10
    assert validate_top_k(5) == 5
    assert validate_top_k("20") == 20
    assert validate_top_k(100) == 100


@pytest.mark.parametrize(
    "invalid_input",
    [
        True,
        False,
        0,
        -1,
        101,
        "",
        "abc",
        "101",
        "0",
    ],
)
def test_validate_top_k_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_top_k(invalid_input)
    assert excinfo.value.status_code == 400


# ---------------------------------------------------------------------------
# Format Validators
# ---------------------------------------------------------------------------


def test_validate_email_valid():
    assert validate_email("test@example.com") == "test@example.com"
    assert validate_email("  user@domain.co.uk  ") == "user@domain.co.uk"


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        None,
        "not-an-email",
        "test@.com",
        "@example.com",
    ],
)
def test_validate_email_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_email(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_url_valid():
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("  http://test.org:8000  ") == "http://test.org:8000"


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        None,
        "not-a-url",
        "htt://invalid",
    ],
)
def test_validate_url_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_url(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_uuid_valid():
    valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
    assert validate_uuid(valid_uuid) == valid_uuid
    assert validate_uuid(f"  {valid_uuid}  ") == valid_uuid


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        None,
        "not-a-uuid",
        "123e4567-e89b-12d3-a456",
    ],
)
def test_validate_uuid_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_uuid(invalid_input)
    assert excinfo.value.status_code == 400


# ---------------------------------------------------------------------------
# Enum and List Validators
# ---------------------------------------------------------------------------


def test_validate_connectors_valid():
    assert validate_connectors(None) == []
    assert validate_connectors(["GITHUB_CONNECTOR", "SLACK_CONNECTOR"]) == [
        "GITHUB_CONNECTOR",
        "SLACK_CONNECTOR",
    ]
    assert validate_connectors(["  my-connector_123  "]) == ["my-connector_123"]


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a list",
        [123],
        [True],
        [""],
        ["   "],
        ["invalid connector!"],
        ["connector 1"],
    ],
)
def test_validate_connectors_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_connectors(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_research_mode_valid():
    assert validate_research_mode(None) == "QNA"
    assert validate_research_mode("QNA") == "QNA"
    assert validate_research_mode("  qna  ") == "QNA"


@pytest.mark.parametrize(
    "invalid_input",
    [
        123,
        "",
        "   ",
        "INVALID",
    ],
)
def test_validate_research_mode_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_research_mode(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_search_mode_valid():
    assert validate_search_mode(None) == "CHUNKS"
    assert validate_search_mode("CHUNKS") == "CHUNKS"
    assert validate_search_mode("  documents  ") == "DOCUMENTS"


@pytest.mark.parametrize(
    "invalid_input",
    [
        123,
        "",
        "   ",
        "INVALID",
    ],
)
def test_validate_search_mode_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_search_mode(invalid_input)
    assert excinfo.value.status_code == 400


# ---------------------------------------------------------------------------
# Complex Validators
# ---------------------------------------------------------------------------


def test_validate_messages_valid():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    assert validate_messages(messages) == messages

    # Test trimming
    assert validate_messages([{"role": "user", "content": "  trimmed  "}]) == [
        {"role": "user", "content": "trimmed"}
    ]


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a list",
        [],
        [123],
        [{"role": "user"}],  # Missing content
        [{"content": "hi"}],  # Missing role
        [{"role": "invalid", "content": "hi"}],  # Invalid role
        [{"role": "user", "content": 123}],  # Non-string content
        [{"role": "user", "content": ""}],  # Empty content
        [{"role": "user", "content": "   "}],  # Whitespace-only content
    ],
)
def test_validate_messages_invalid(invalid_input):
    with pytest.raises(HTTPException) as excinfo:
        validate_messages(invalid_input)
    assert excinfo.value.status_code == 400


def test_validate_connector_config_valid():
    # Pass-through for unknown connector
    assert validate_connector_config("UNKNOWN", {"any": "value"}) == {"any": "value"}

    # Known connector with required fields
    config = {"SERPER_API_KEY": "secret"}
    assert validate_connector_config("SERPER_API", config) == config

    # Specific format validation (URL)
    searxng_config = {"SEARXNG_HOST": "https://search.example.com"}
    assert validate_connector_config("SEARXNG_API", searxng_config) == searxng_config


def test_validate_connector_config_invalid():
    # Invalid config type
    with pytest.raises(ValueError):
        validate_connector_config("SERPER_API", "not a dict")

    # Missing required key
    with pytest.raises(ValueError):
        validate_connector_config("SERPER_API", {})

    # Unexpected keys
    with pytest.raises(ValueError):
        validate_connector_config(
            "SERPER_API", {"SERPER_API_KEY": "secret", "UNEXPECTED": "value"}
        )

    # Empty required key
    with pytest.raises(ValueError):
        validate_connector_config("SERPER_API", {"SERPER_API_KEY": ""})

    # Invalid URL format in SEARXNG_API
    with pytest.raises(ValueError):
        validate_connector_config("SEARXNG_API", {"SEARXNG_HOST": "not-a-url"})

    # WEBCRAWLER_CONNECTOR custom validation: malformed INITIAL_URLS rejected.
    with pytest.raises(ValueError):
        validate_connector_config(
            "WEBCRAWLER_CONNECTOR", {"INITIAL_URLS": "not-a-url"}
        )
