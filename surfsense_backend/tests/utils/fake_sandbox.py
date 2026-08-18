"""Shared in-memory implementation of the sandbox session contract."""

from __future__ import annotations

from collections.abc import Callable

from app.sandbox import ExecResult


class FakeSandboxSession:
    session_id = "test-sandbox"

    def __init__(
        self,
        files: dict[str, bytes] | None = None,
        *,
        command_handler: Callable[[str], ExecResult] | None = None,
    ) -> None:
        self.files = dict(files or {})
        self.writes: dict[str, bytes] = {}
        self.commands: list[str] = []
        self.command_handler = command_handler
        self.terminated = False

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        return ExecResult("", 0)

    async def run_command(self, command: str) -> ExecResult:
        self.commands.append(command)
        return (
            self.command_handler(command)
            if self.command_handler is not None
            else ExecResult("", 0)
        )

    async def read_file(self, path: str) -> bytes:
        try:
            return self.files[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    async def write_file(self, path: str, data: bytes) -> None:
        self.files[path] = data
        self.writes[path] = data

    async def terminate(self) -> None:
        self.terminated = True
