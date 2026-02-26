from unittest.mock import MagicMock

import pytest

from app.indexing_pipeline.document_summarizer import summarize_document

pytestmark = pytest.mark.unit


@pytest.mark.usefixtures("patched_summarizer_chain")
async def test_without_metadata_returns_raw_summary():
    """Summarizer returns the LLM output directly when no metadata is provided."""
    result = await summarize_document("# Content", llm=MagicMock(model="gpt-4"))

    assert result == "The summary."


@pytest.mark.usefixtures("patched_summarizer_chain")
async def test_with_metadata_includes_metadata_values_in_output():
    """Non-empty metadata values are prepended to the summary output."""
    result = await summarize_document(
        "# Content",
        llm=MagicMock(model="gpt-4"),
        metadata={"author": "Alice", "source": "Notion"},
    )

    assert "Alice" in result
    assert "Notion" in result


@pytest.mark.usefixtures("patched_summarizer_chain")
async def test_with_metadata_omits_empty_fields_from_output():
    """Empty metadata fields are omitted from the summary output."""
    result = await summarize_document(
        "# Content",
        llm=MagicMock(model="gpt-4"),
        metadata={"author": "Alice", "description": ""},
    )

    assert "Alice" in result
    assert "description" not in result.lower()
