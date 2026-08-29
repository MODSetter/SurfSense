"""OpenSandbox provider (self-hosted).

Sandboxes are created against `opensandbox-server`, which spawns them as
sibling containers on the host daemon. The backend's only coupling is HTTP plus
an API key.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import NoReturn

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox, SandboxManager
from opensandbox.config import ConnectionConfig
from opensandbox.exceptions import SandboxApiException, SandboxReadyTimeoutException
from opensandbox.models import NetworkPolicy, SandboxFilter

from app.config import config as app_config

from ..file_stream import read_file_stream_via_commands
from ..protocol import ExecResult

logger = logging.getLogger(__name__)

THREAD_METADATA_KEY = "surfsense_thread"

# OpenSandbox requires the image service entrypoint explicitly; PYTHON_VERSION
# selects the image's Python runtime (see docker/sandbox/Dockerfile).
_ENTRYPOINT = ["/opt/code-interpreter/code-interpreter.sh"]
_ENV = {"PYTHON_VERSION": "3.12"}
_RUNNING_STATES = {"RUNNING", "PENDING"}

_LANGUAGES = {
    "python": SupportedLanguage.PYTHON,
    "bash": SupportedLanguage.BASH,
    "javascript": SupportedLanguage.JAVASCRIPT,
    "typescript": SupportedLanguage.TYPESCRIPT,
}


def _raise_normalized(
    exc: Exception, *, operation: str, path: str | None = None
) -> NoReturn:
    """Keep provider diagnostics in logs while exposing the sandbox contract."""
    logger.warning(
        "OpenSandbox %s failed%s",
        operation,
        f" for {path}" if path else "",
        exc_info=exc,
    )
    if isinstance(exc, SandboxApiException):
        if exc.status_code == 404 and path is not None:
            raise FileNotFoundError(path) from None
        if exc.status_code in {401, 403}:
            raise PermissionError(f"Sandbox {operation} was denied") from None
        if exc.status_code in {408, 504}:
            raise TimeoutError(f"Sandbox {operation} timed out") from None
        raise RuntimeError(f"Sandbox {operation} failed") from None
    if isinstance(
        exc, (TimeoutError, asyncio.TimeoutError, SandboxReadyTimeoutException)
    ):
        raise TimeoutError(f"Sandbox {operation} timed out") from None
    raise exc


def _to_result(execution) -> ExecResult:
    """Flatten an SDK execution into the provider-neutral result shape."""
    if execution.error is not None:
        return ExecResult(output=str(execution), exit_code=1)
    return ExecResult(output=str(execution), exit_code=execution.exit_code or 0)


class OpenSandboxSession:
    """One sandbox plus its persistent code-interpreter kernel."""

    def __init__(self, sandbox: Sandbox, ttl_seconds: int) -> None:
        self._sandbox = sandbox
        self._ttl_seconds = ttl_seconds
        self._last_renewed = time.monotonic()
        self._renew_mu = asyncio.Lock()
        self._interpreter: CodeInterpreter | None = None
        self._interpreter_mu = asyncio.Lock()

    @property
    def session_id(self) -> str:
        return self._sandbox.id

    async def _get_interpreter(self) -> CodeInterpreter:
        async with self._interpreter_mu:
            if self._interpreter is None:
                self._interpreter = await CodeInterpreter.create(sandbox=self._sandbox)
            return self._interpreter

    async def _renew_if_needed(self) -> None:
        """Extend the remote expiry when activity resumes after half the TTL."""
        if time.monotonic() - self._last_renewed < self._ttl_seconds / 2:
            return
        async with self._renew_mu:
            if time.monotonic() - self._last_renewed < self._ttl_seconds / 2:
                return
            await self._sandbox.renew(timedelta(seconds=self._ttl_seconds))
            self._last_renewed = time.monotonic()

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        lang = _LANGUAGES.get(language.lower())
        if lang is None:
            return ExecResult(
                output=f"Unsupported language: {language}. Use python or bash.",
                exit_code=1,
            )
        try:
            await self._renew_if_needed()
            interpreter = await self._get_interpreter()
            return _to_result(await interpreter.codes.run(code, language=lang))
        except Exception as exc:
            _raise_normalized(exc, operation="execution")

    async def run_command(self, command: str) -> ExecResult:
        try:
            await self._renew_if_needed()
            return _to_result(await self._sandbox.commands.run(command))
        except Exception as exc:
            _raise_normalized(exc, operation="command")

    async def read_file(self, path: str) -> bytes:
        try:
            await self._renew_if_needed()
            return await self._sandbox.files.read_bytes(path)
        except Exception as exc:
            _raise_normalized(exc, operation="read", path=path)

    def read_file_stream(self, path: str, *, chunk_size: int = 1024 * 1024):
        # OpenSandbox 0.1.x exposes read_bytes but no streamed download.
        return read_file_stream_via_commands(
            self.run_command, path, chunk_size=chunk_size
        )

    async def write_file(self, path: str, data: bytes) -> None:
        try:
            await self._renew_if_needed()
            await self._sandbox.files.write_file(path, data)
        except Exception as exc:
            _raise_normalized(exc, operation="write", path=path)

    async def terminate(self) -> None:
        await self._sandbox.kill()


class OpenSandboxProvider:
    def __init__(self) -> None:
        # use_server_proxy keeps sandbox endpoints reachable from wherever the
        # backend runs: without it the SDK talks straight to a host-published
        # port that only resolves inside docker's network.
        self._config = ConnectionConfig(
            domain=app_config.OPENSANDBOX_DOMAIN,
            api_key=app_config.OPENSANDBOX_API_KEY,
            use_server_proxy=True,
            # Covers every management call, creation included — and creation
            # blocks on the server pulling the image when it is not already on
            # the host daemon.
            request_timeout=timedelta(
                seconds=app_config.SANDBOX_OPERATION_TIMEOUT_SECONDS
            ),
        )
        self._ttl = app_config.SANDBOX_IDLE_TTL_SECONDS
        self._manager: SandboxManager | None = None
        self._manager_mu = asyncio.Lock()

    async def _get_manager(self) -> SandboxManager:
        async with self._manager_mu:
            if self._manager is None:
                self._manager = await SandboxManager.create(
                    connection_config=self._config
                )
            return self._manager

    async def _find_live(self, thread_id: str) -> str | None:
        manager = await self._get_manager()
        page = await manager.list_sandbox_infos(
            SandboxFilter(metadata={THREAD_METADATA_KEY: thread_id})
        )
        for info in page.sandbox_infos:
            if info.status.state.upper() in _RUNNING_STATES:
                return info.id
        return None

    async def get_or_create_session(self, thread_id: str) -> OpenSandboxSession:
        existing = await self._find_live(thread_id)
        if existing is not None:
            try:
                sandbox = await Sandbox.connect(
                    existing, connection_config=self._config
                )
                # The sandbox may be near its expiry; adopting it without a
                # renew hands the caller a session that dies mid-task.
                await sandbox.renew(timedelta(seconds=self._ttl))
                logger.info("Adopted sandbox %s for thread %s", existing, thread_id)
                return OpenSandboxSession(sandbox, self._ttl)
            except Exception:
                logger.warning(
                    "Could not adopt sandbox %s — creating a new one",
                    existing,
                    exc_info=True,
                )

        sandbox = await Sandbox.create(
            app_config.SANDBOX_IMAGE,
            connection_config=self._config,
            entrypoint=_ENTRYPOINT,
            env=_ENV,
            metadata={THREAD_METADATA_KEY: thread_id},
            network_policy=NetworkPolicy(default_action="deny"),
            resource={"cpu": "1", "memory": "2Gi"},
            timeout=timedelta(seconds=self._ttl),
        )
        logger.info("Created sandbox %s for thread %s", sandbox.id, thread_id)
        return OpenSandboxSession(sandbox, self._ttl)

    async def terminate_session(self, thread_id: str) -> None:
        sandbox_id = await self._find_live(thread_id)
        if sandbox_id is None:
            return
        manager = await self._get_manager()
        await manager.kill_sandbox(sandbox_id)
        logger.info("Killed sandbox %s for thread %s", sandbox_id, thread_id)
