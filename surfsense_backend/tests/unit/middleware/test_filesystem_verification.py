import pytest

from app.agents.new_chat.middleware.filesystem import SurfSenseFilesystemMiddleware

pytestmark = pytest.mark.unit


class _BackendWithRawRead:
    def __init__(self, content: str) -> None:
        self._content = content

    def read(self, file_path: str, offset: int = 0, limit: int = 200000) -> str:
        del file_path, offset, limit
        return "     1\tline1\n     2\tline2"

    async def aread(self, file_path: str, offset: int = 0, limit: int = 200000) -> str:
        return self.read(file_path, offset, limit)

    def read_raw(self, file_path: str) -> str:
        del file_path
        return self._content

    async def aread_raw(self, file_path: str) -> str:
        return self.read_raw(file_path)


class _RuntimeNoSuggestedPath:
    state = {"file_operation_contract": {}}


def test_verify_written_content_prefers_raw_sync() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    expected = "line1\nline2"
    backend = _BackendWithRawRead(expected)

    verify_error = middleware._verify_written_content_sync(
        backend=backend,
        path="/note.md",
        expected_content=expected,
    )

    assert verify_error is None


def test_contract_suggested_path_falls_back_to_notes_md() -> None:
    suggested = SurfSenseFilesystemMiddleware._get_contract_suggested_path(
        _RuntimeNoSuggestedPath()
    )
    assert suggested == "/notes.md"


@pytest.mark.asyncio
async def test_verify_written_content_prefers_raw_async() -> None:
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    expected = "line1\nline2"
    backend = _BackendWithRawRead(expected)

    verify_error = await middleware._verify_written_content_async(
        backend=backend,
        path="/note.md",
        expected_content=expected,
    )

    assert verify_error is None
