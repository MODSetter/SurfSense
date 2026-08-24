import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.artifacts.persistence import ArtifactFileRole
from app.artifacts.storage import store_artifact_file_stream
from app.file_storage.backends.local import LocalFileBackend


async def _chunks(*values: bytes):
    for value in values:
        yield value


async def test_local_backend_stream_write_and_range_read(tmp_path):
    backend = LocalFileBackend(str(tmp_path))
    await backend.put_stream("video/out.mp4", _chunks(b"abc", b"def"))

    assert (
        b"".join([chunk async for chunk in backend.open_range("video/out.mp4", 1, 4)])
        == b"bcde"
    )


async def test_store_stream_hashes_and_sizes_in_one_pass(tmp_path):
    backend = LocalFileBackend(str(tmp_path))
    session = SimpleNamespace(add=Mock())
    payload = b"narrated-video"

    record = await store_artifact_file_stream(
        session,
        artifact_id=1,
        workspace_id=2,
        role=ArtifactFileRole.PRIMARY,
        chunks=_chunks(payload[:5], payload[5:]),
        filename="out.mp4",
        mime_type="video/mp4",
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        backend=backend,
    )

    assert record.size_bytes == len(payload)
    assert record.checksum_sha256 == hashlib.sha256(payload).hexdigest()
    assert (
        b"".join([chunk async for chunk in backend.open_stream(record.storage_key)])
        == payload
    )
    session.add.assert_called_once_with(record)


async def test_store_stream_deletes_blob_on_hash_mismatch(tmp_path):
    backend = LocalFileBackend(str(tmp_path))

    with pytest.raises(ValueError, match="changed after verification"):
        await store_artifact_file_stream(
            SimpleNamespace(add=Mock()),
            artifact_id=1,
            workspace_id=2,
            role=ArtifactFileRole.PRIMARY,
            chunks=_chunks(b"changed"),
            filename="out.mp4",
            mime_type="video/mp4",
            expected_sha256="0" * 64,
            backend=backend,
        )

    assert list(tmp_path.rglob("*.mp4")) == []
