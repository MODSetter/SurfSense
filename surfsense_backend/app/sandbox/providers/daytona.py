"""Daytona provider (cloud).

Extracted from ``shared/middleware/filesystem/sandbox.py``: label-based
discovery, broken-state recovery and create-from-snapshot are that module's
proven logic, moved behind the protocol. The caching and locking that used to
live alongside them now belong to the registry.

The SDK is synchronous, so every call crosses ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets

from daytona import (
    CreateSandboxFromSnapshotParams,
    Daytona,
    DaytonaConfig,
    SandboxState,
)

from app.config import config as app_config

from ..protocol import ExecResult

logger = logging.getLogger(__name__)

THREAD_LABEL_KEY = "surfsense_thread"
_DEFAULT_TIMEOUT = 300
_START_TIMEOUT = 60


def _wrap_as_python(code: str) -> str:
    """Wrap code in a unique-sentinel heredoc.

    Daytona exposes commands, not a kernel, so Python arrives as a shell
    command and state does not carry across calls.
    """
    sentinel = f"_PYEOF_{secrets.token_hex(8)}"
    return f"python3 << '{sentinel}'\n{code}\n{sentinel}"


class DaytonaSession:
    def __init__(self, sandbox, client: Daytona) -> None:
        self._sandbox = sandbox
        self._client = client

    @property
    def session_id(self) -> str:
        return self._sandbox.id

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        command = _wrap_as_python(code) if language.lower() == "python" else code
        return await self.run_command(command)

    async def run_command(self, command: str) -> ExecResult:
        def _run() -> ExecResult:
            result = self._sandbox.process.exec(command, timeout=_DEFAULT_TIMEOUT)
            return ExecResult(
                output=result.result or "",
                exit_code=result.exit_code or 0,
            )

        return await asyncio.to_thread(_run)

    async def read_file(self, path: str) -> bytes:
        data = await asyncio.to_thread(self._sandbox.fs.download_file, path)
        if data is None:
            raise FileNotFoundError(path)
        return data

    async def write_file(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self._sandbox.fs.upload_file, data, path)

    async def terminate(self) -> None:
        await asyncio.to_thread(self._client.delete, self._sandbox)


class DaytonaProvider:
    def __init__(self) -> None:
        self._client: Daytona | None = None
        self._client_mu = asyncio.Lock()

    async def _get_client(self) -> Daytona:
        async with self._client_mu:
            if self._client is None:
                self._client = Daytona(
                    DaytonaConfig(
                        api_key=app_config.DAYTONA_API_KEY,
                        api_url=app_config.DAYTONA_API_URL,
                        target=app_config.DAYTONA_TARGET,
                    )
                )
            return self._client

    def _create_params(self, labels: dict[str, str]) -> CreateSandboxFromSnapshotParams:
        return CreateSandboxFromSnapshotParams(
            language="python",
            labels=labels,
            snapshot=app_config.DAYTONA_SNAPSHOT_ID,
            network_block_all=True,
            auto_stop_interval=10,
            auto_delete_interval=60,
        )

    def _find_one(self, client: Daytona, labels: dict[str, str]):
        """The thread's sandbox, or None.

        ``find_one`` was dropped from the SDK; ``list`` reports absence as an
        empty page rather than by raising, so only real API failures propagate.
        """
        items = client.list(labels=labels).items
        return items[0] if items else None

    def _find_or_create(self, client: Daytona, thread_id: str):
        labels = {THREAD_LABEL_KEY: thread_id}
        sandbox = self._find_one(client, labels)
        if sandbox is None:
            logger.info("No sandbox for thread %s — creating one", thread_id)
            return client.create(self._create_params(labels))

        if sandbox.state in (
            SandboxState.STOPPED,
            SandboxState.STOPPING,
            SandboxState.ARCHIVED,
        ):
            sandbox.start(timeout=_START_TIMEOUT)
        elif sandbox.state in (
            SandboxState.ERROR,
            SandboxState.BUILD_FAILED,
            SandboxState.DESTROYED,
        ):
            logger.warning(
                "Sandbox %s in unrecoverable state %s — replacing",
                sandbox.id,
                sandbox.state,
            )
            with contextlib.suppress(Exception):
                client.delete(sandbox)
            return client.create(self._create_params(labels))
        elif sandbox.state != SandboxState.STARTED:
            sandbox.wait_for_sandbox_start(timeout=_START_TIMEOUT)

        return sandbox

    async def get_or_create_session(self, thread_id: str) -> DaytonaSession:
        client = await self._get_client()
        sandbox = await asyncio.to_thread(self._find_or_create, client, thread_id)
        return DaytonaSession(sandbox, client)

    async def terminate_session(self, thread_id: str) -> None:
        client = await self._get_client()

        def _kill() -> None:
            sandbox = self._find_one(client, {THREAD_LABEL_KEY: thread_id})
            if sandbox is None:
                return
            client.delete(sandbox)
            logger.info("Deleted sandbox %s for thread %s", sandbox.id, thread_id)

        await asyncio.to_thread(_kill)
