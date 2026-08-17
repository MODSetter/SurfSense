import pytest

from app.artifacts.service import (
    ArtifactFileInput,
    _artifact_format,
    _validate_files,
    _validated_files,
)


def test_validate_files_accepts_primary_and_rejects_duplicate_or_source_roles():
    primary = ArtifactFileInput(b"pdf", "out.pdf", "application/pdf", "primary")
    _validate_files([primary])

    with pytest.raises(ValueError, match="at most one"):
        _validate_files([primary, primary])
    with pytest.raises(ValueError, match=r"primary.*preview"):
        _validate_files(
            [ArtifactFileInput(b"source", "out.py", "text/x-python", "source")]
        )


def test_artifact_format_uses_markdown_or_primary_extension():
    assert _artifact_format([]) == "markdown"
    files = _validated_files(
        [ArtifactFileInput(b"pdf", "Report.PDF", "application/pdf")]
    )
    assert _artifact_format(files) == "pdf"
