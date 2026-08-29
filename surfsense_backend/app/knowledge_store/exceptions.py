"""The store's errors: one tagged failure, discriminated by operation."""

from __future__ import annotations

from typing import Literal

Operation = Literal["record", "read", "lock", "project", "seed", "working_copy", "push"]


class KnowledgeStoreError(RuntimeError):
    """A store operation failed. ``operation`` says which, for the caller to log."""

    def __init__(self, operation: Operation, message: str) -> None:
        super().__init__(f"[{operation}] {message}")
        self.operation = operation
        self.message = message


class KnowledgeStoreLockError(KnowledgeStoreError):
    """A workspace lock could not be acquired, or a hold expired mid-block."""

    def __init__(self, message: str) -> None:
        super().__init__("lock", message)


class GitPushError(KnowledgeStoreError):
    """send-pack rejected the update (non-fast-forward, auth, or network)."""

    def __init__(self, message: str) -> None:
        super().__init__("push", message)
