from datetime import timedelta
from types import SimpleNamespace

import pytest
from opensandbox.exceptions import SandboxApiException

from app.config import config as app_config
from app.sandbox.providers.opensandbox import OpenSandboxProvider, OpenSandboxSession


class _Files:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def read_bytes(self, _path: str) -> bytes:
        raise self.exc


def _session(exc: Exception) -> OpenSandboxSession:
    sandbox = SimpleNamespace(id="sandbox-1", files=_Files(exc))
    return OpenSandboxSession(sandbox, ttl_seconds=900)


def test_provider_uses_the_shared_sandbox_operation_budget(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "SANDBOX_OPERATION_TIMEOUT_SECONDS", 37)

    provider = OpenSandboxProvider()

    assert provider._config.request_timeout == timedelta(seconds=37)


async def test_read_file_normalizes_provider_404() -> None:
    session = _session(
        SandboxApiException(
            "provider URL and request id",
            status_code=404,
            request_id="secret-request",
        )
    )

    with pytest.raises(FileNotFoundError) as raised:
        await session.read_file("/workspace/missing.pdf")

    assert str(raised.value) == "/workspace/missing.pdf"
    assert "secret-request" not in str(raised.value)


async def test_read_file_hides_other_provider_details() -> None:
    session = _session(
        SandboxApiException(
            "provider URL and request id",
            status_code=500,
            request_id="secret-request",
        )
    )

    with pytest.raises(RuntimeError, match="Sandbox read failed") as raised:
        await session.read_file("/workspace/report.pdf")

    assert "secret-request" not in str(raised.value)


@pytest.mark.parametrize(
    ("status_code", "error_type", "message"),
    [
        (403, PermissionError, "Sandbox read was denied"),
        (504, TimeoutError, "Sandbox read timed out"),
    ],
)
async def test_read_file_normalizes_permission_and_timeout_failures(
    status_code: int, error_type: type[Exception], message: str
) -> None:
    session = _session(SandboxApiException("provider detail", status_code=status_code))

    with pytest.raises(error_type, match=message):
        await session.read_file("/workspace/report.pdf")
