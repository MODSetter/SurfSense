from types import SimpleNamespace

import pytest

from app.artifacts.service import (
    ArtifactFileInput,
    _path_for_revision,
    _validate_files,
)
from app.file_storage.persistence.models import DocumentFile


def test_validate_files_accepts_one_source_and_rejects_duplicate_roles():
    source = ArtifactFileInput(b"source", "out.py", "text/x-python", "source")
    _validate_files([source])

    with pytest.raises(ValueError, match="at most one"):
        _validate_files([source, source])


def test_generated_file_roles_have_a_database_uniqueness_guard():
    index = next(
        index
        for index in DocumentFile.__table__.indexes
        if index.name == "uq_document_files_generated_role"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["document_id", "role"]


def test_revision_requires_the_authoritative_document_path():
    document = SimpleNamespace(
        title="Guessable title",
        path=None,
        unique_identifier_hash="missing",
    )

    with pytest.raises(ValueError, match="has not been recorded"):
        _path_for_revision(document)
