import pytest

from app.artifacts.service import (
    ArtifactFileInput,
    _artifact_format,
    _validate_files,
    _validated_files,
)


def test_validate_files_accepts_one_source_and_rejects_duplicate_roles():
    source = ArtifactFileInput(b"source", "out.py", "text/x-python", "source")
    _validate_files([source])

    with pytest.raises(ValueError, match="at most one"):
        _validate_files([source, source])


def test_artifact_format_uses_markdown_or_primary_extension():
    assert _artifact_format([]) == "markdown"
    files = _validated_files(
        [ArtifactFileInput(b"pdf", "Report.PDF", "application/pdf")]
    )
    assert _artifact_format(files) == "pdf"
