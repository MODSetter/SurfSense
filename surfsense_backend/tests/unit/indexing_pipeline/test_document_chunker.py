import pytest

from app.indexing_pipeline.document_chunker import chunk_text, chunk_text_hybrid

pytestmark = pytest.mark.unit


@pytest.mark.usefixtures("patched_chunker_instance", "patched_code_chunker_instance")
def test_uses_code_chunker_when_flag_is_true():
    """Code chunker is selected when use_code_chunker=True."""
    result = chunk_text("def foo(): pass", use_code_chunker=True)

    assert result == ["code chunk"]


@pytest.mark.usefixtures("patched_chunker_instance", "patched_code_chunker_instance")
def test_uses_default_chunker_when_flag_is_false():
    """Default prose chunker is selected when use_code_chunker=False."""
    result = chunk_text("Some prose text.", use_code_chunker=False)

    assert result == ["prose chunk"]


@pytest.mark.usefixtures("patched_chunker_instance")
def test_hybrid_keeps_last_table_row_when_text_ends_without_newline():
    """A table closing the document keeps its last row in the table chunk."""
    table = "| a | b |\n|---|---|\n| 1 | 2 |"

    result = chunk_text_hybrid(f"Intro.\n\n{table}")

    assert result == ["prose chunk", table]
