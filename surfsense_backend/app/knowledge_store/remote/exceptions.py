"""Errors for adding or talking to a workspace git remote."""

from __future__ import annotations

from typing import Literal

RemoteErrorCode = Literal[
    "not_git_native",
    "already_exists",
    "not_empty",
    "invalid_spec",
    "missing",
    "forge",
]


class RemoteError(Exception):
    """A git-remote verb failed. ``code`` is the HTTP mapping."""

    def __init__(self, code: RemoteErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
