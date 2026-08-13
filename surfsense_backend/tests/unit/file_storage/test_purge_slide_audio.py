"""Deleting a video document also removes its offloaded slide audio.

Slide audio is object storage keyed from ``artifact_metadata``, not an
``ArtifactFile`` row, so it would leak if the purge only walked the file
tables.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.file_storage.service import purge_document_blobs

pytestmark = pytest.mark.unit


def _result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_purge_deletes_slide_audio_from_metadata():
    metadata = {
        "slides": [
            {"slide_number": 1, "audio_storage_key": "k1", "storage_backend": "s3"},
            {"slide_number": 2, "audio_storage_key": "k2", "storage_backend": "s3"},
            {"slide_number": 3},  # no audio → skipped
        ]
    }
    session = AsyncMock()
    session.execute.side_effect = [
        _result([]),  # document_files
        _result([]),  # artifact_files
        _result([(metadata,)]),  # video artifact metadata
    ]

    backend = AsyncMock()
    await purge_document_blobs(session, document_ids=[7], backend=backend)

    deleted = {call.args[0] for call in backend.delete.await_args_list}
    assert deleted == {"k1", "k2"}
