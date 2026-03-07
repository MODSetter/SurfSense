import pytest

from app.indexing_pipeline.document_chunker import chunk_text

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
