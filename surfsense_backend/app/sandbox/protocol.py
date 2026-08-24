"""Provider-agnostic sandbox contract.

One session per chat thread. Providers differ in how a session is obtained and
torn down; everything above this module talks only to these three types.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class ExecResult:
    """Outcome of a single execution inside a sandbox session."""

    output: str
    exit_code: int
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@runtime_checkable
class SandboxSession(Protocol):
    """A live sandbox bound to one chat thread."""

    @property
    def session_id(self) -> str: ...

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        """Run code in the persistent interpreter, keeping state across calls."""
        ...

    async def run_command(self, command: str) -> ExecResult:
        """Run a shell command. Each call is a fresh process."""
        ...

    async def read_file(self, path: str) -> bytes: ...

    def read_file_stream(
        self, path: str, *, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]: ...

    async def write_file(self, path: str, data: bytes) -> None: ...

    async def terminate(self) -> None: ...


@runtime_checkable
class SandboxProvider(Protocol):
    """Creates and rediscovers sessions for a given backend."""

    async def get_or_create_session(self, thread_id: str) -> SandboxSession:
        """Return the thread's session, adopting a live one if it exists.

        Rediscovery matters across backend restarts: the sandbox outlives the
        process that created it, so providers look it up by thread metadata
        before paying to create another.
        """
        ...

    async def terminate_session(self, thread_id: str) -> None:
        """Kill the thread's session if one exists. Must not raise if absent."""
        ...


class SandboxUnavailableError(RuntimeError):
    """Raised when no session can be provided, including at the concurrency cap.

    The message reaches the model as a tool error, so it must say what to do
    next rather than describe internals.
    """
