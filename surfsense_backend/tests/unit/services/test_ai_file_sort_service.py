"""Unit tests for AI file sort service: folder label resolution, date extraction, category sanitization."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ── resolve_root_folder_label ──


def _make_document(document_type: str, connector_id=None):
    doc = MagicMock()
    doc.document_type = document_type
    doc.connector_id = connector_id
    return doc


def _make_connector(connector_type: str):
    conn = MagicMock()
    conn.connector_type = connector_type
    return conn


def test_root_label_uses_connector_type_when_available():
    from app.services.ai_file_sort_service import resolve_root_folder_label

    doc = _make_document("FILE", connector_id=1)
    conn = _make_connector("GOOGLE_DRIVE_CONNECTOR")
    assert resolve_root_folder_label(doc, conn) == "Google Drive"


def test_root_label_falls_back_to_document_type():
    from app.services.ai_file_sort_service import resolve_root_folder_label

    doc = _make_document("SLACK_CONNECTOR")
    assert resolve_root_folder_label(doc, None) == "Slack"


def test_root_label_unknown_doctype_returns_raw_value():
    from app.services.ai_file_sort_service import resolve_root_folder_label

    doc = _make_document("UNKNOWN_TYPE")
    assert resolve_root_folder_label(doc, None) == "UNKNOWN_TYPE"


# ── resolve_date_folder ──


def test_date_folder_from_updated_at():
    from app.services.ai_file_sort_service import resolve_date_folder

    doc = MagicMock()
    doc.updated_at = datetime(2025, 3, 15, 10, 30, 0, tzinfo=UTC)
    doc.created_at = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert resolve_date_folder(doc) == "2025-03-15"


def test_date_folder_falls_back_to_created_at():
    from app.services.ai_file_sort_service import resolve_date_folder

    doc = MagicMock()
    doc.updated_at = None
    doc.created_at = datetime(2024, 12, 25, 23, 59, 0, tzinfo=UTC)
    assert resolve_date_folder(doc) == "2024-12-25"


def test_date_folder_both_none_uses_today():
    from app.services.ai_file_sort_service import resolve_date_folder

    doc = MagicMock()
    doc.updated_at = None
    doc.created_at = None
    result = resolve_date_folder(doc)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    assert result == today


# ── sanitize_category_folder_name ──


def test_sanitize_normal_value():
    from app.services.ai_file_sort_service import sanitize_category_folder_name

    assert sanitize_category_folder_name("Machine Learning") == "Machine Learning"


def test_sanitize_strips_special_chars():
    from app.services.ai_file_sort_service import sanitize_category_folder_name

    assert sanitize_category_folder_name("Tax/Reports!") == "TaxReports"


def test_sanitize_empty_returns_fallback():
    from app.services.ai_file_sort_service import sanitize_category_folder_name

    assert sanitize_category_folder_name("") == "Uncategorized"
    assert sanitize_category_folder_name(None) == "Uncategorized"


def test_sanitize_truncates_long_names():
    from app.services.ai_file_sort_service import sanitize_category_folder_name

    long_name = "A" * 100
    result = sanitize_category_folder_name(long_name)
    assert len(result) <= 50


# ── generate_ai_taxonomy ──


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_parses_json():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = '{"category": "Science", "subcategory": "Physics"}'
    mock_llm.ainvoke.return_value = mock_result

    cat, sub = await generate_ai_taxonomy(
        "Physics Paper", "Some science document about physics", mock_llm
    )
    assert cat == "Science"
    assert sub == "Physics"


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_handles_markdown_code_block():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = (
        '```json\n{"category": "Finance", "subcategory": "Tax Reports"}\n```'
    )
    mock_llm.ainvoke.return_value = mock_result

    cat, sub = await generate_ai_taxonomy("Tax Doc", "A tax report document", mock_llm)
    assert cat == "Finance"
    assert sub == "Tax Reports"


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_includes_title_in_prompt():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = '{"category": "Engineering", "subcategory": "Backend"}'
    mock_llm.ainvoke.return_value = mock_result

    await generate_ai_taxonomy("API Design Guide", "content about REST APIs", mock_llm)

    prompt_text = mock_llm.ainvoke.call_args[0][0][0].content
    assert "API Design Guide" in prompt_text
    assert "content about REST APIs" in prompt_text


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_fallback_on_error():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = RuntimeError("LLM down")

    cat, sub = await generate_ai_taxonomy("Title", "some content", mock_llm)
    assert cat == "Uncategorized"
    assert sub == "General"


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_fallback_on_empty_content():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    cat, sub = await generate_ai_taxonomy("Title", "", mock_llm)
    assert cat == "Uncategorized"
    assert sub == "General"
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_generate_ai_taxonomy_fallback_on_invalid_json():
    from app.services.ai_file_sort_service import generate_ai_taxonomy

    mock_llm = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = "not valid json at all"
    mock_llm.ainvoke.return_value = mock_result

    cat, sub = await generate_ai_taxonomy("Title", "some content", mock_llm)
    assert cat == "Uncategorized"
    assert sub == "General"


# ── taxonomy caching ──


def test_get_cached_taxonomy_returns_none_when_no_metadata():
    from app.services.ai_file_sort_service import _get_cached_taxonomy

    doc = MagicMock()
    doc.document_metadata = None
    assert _get_cached_taxonomy(doc) is None


def test_get_cached_taxonomy_returns_none_when_keys_missing():
    from app.services.ai_file_sort_service import _get_cached_taxonomy

    doc = MagicMock()
    doc.document_metadata = {"some_other_key": "value"}
    assert _get_cached_taxonomy(doc) is None


def test_get_cached_taxonomy_returns_cached_values():
    from app.services.ai_file_sort_service import _get_cached_taxonomy

    doc = MagicMock()
    doc.document_metadata = {
        "ai_sort_category": "Finance",
        "ai_sort_subcategory": "Tax Reports",
    }
    assert _get_cached_taxonomy(doc) == ("Finance", "Tax Reports")


def test_set_cached_taxonomy_persists_on_metadata():
    from app.services.ai_file_sort_service import _set_cached_taxonomy

    doc = MagicMock()
    doc.document_metadata = {"existing_key": "keep_me"}
    _set_cached_taxonomy(doc, "Science", "Physics")
    assert doc.document_metadata["ai_sort_category"] == "Science"
    assert doc.document_metadata["ai_sort_subcategory"] == "Physics"
    assert doc.document_metadata["existing_key"] == "keep_me"


def test_set_cached_taxonomy_creates_metadata_when_none():
    from app.services.ai_file_sort_service import _set_cached_taxonomy

    doc = MagicMock()
    doc.document_metadata = None
    _set_cached_taxonomy(doc, "Engineering", "Backend")
    assert doc.document_metadata == {
        "ai_sort_category": "Engineering",
        "ai_sort_subcategory": "Backend",
    }


# ── _build_path_segments ──


def test_build_path_segments_structure():
    from app.services.ai_file_sort_service import _build_path_segments

    segments = _build_path_segments("Google Drive", "2025-03-15", "Science", "Physics")
    assert len(segments) == 4
    assert segments[0] == {
        "name": "Google Drive",
        "metadata": {"ai_sort": True, "ai_sort_level": 1},
    }
    assert segments[1] == {
        "name": "2025-03-15",
        "metadata": {"ai_sort": True, "ai_sort_level": 2},
    }
    assert segments[2] == {
        "name": "Science",
        "metadata": {"ai_sort": True, "ai_sort_level": 3},
    }
    assert segments[3] == {
        "name": "Physics",
        "metadata": {"ai_sort": True, "ai_sort_level": 4},
    }
