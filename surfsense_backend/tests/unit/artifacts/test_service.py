from types import SimpleNamespace

import pytest

from app.artifacts.service import (
    ArtifactFileInput,
    _path_for_revision,
    _validate_files,
)


def test_validate_files_accepts_one_source_and_rejects_duplicate_roles():
    source = ArtifactFileInput(b"source", "out.py", "text/x-python", "source")
    _validate_files([source])

    with pytest.raises(ValueError, match="at most one"):
        _validate_files([source, source])


async def test_revision_path_is_never_guessed_from_title():
    document = SimpleNamespace(
        title="Guessable title",
        document_metadata={},
        unique_identifier_hash="missing",
    )

    with pytest.raises(ValueError, match="has not been recorded"):
        await _path_for_revision(
            document,
            workspace_id=1,
            working_copy_root=None,
        )
