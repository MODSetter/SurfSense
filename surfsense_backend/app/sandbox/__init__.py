"""Provider-agnostic sandboxed code execution."""

from .factory import is_sandbox_enabled
from .protocol import (
    ExecResult,
    SandboxProvider,
    SandboxSession,
    SandboxUnavailableError,
)
from .registry import SandboxRegistry, get_registry

__all__ = [
    "ExecResult",
    "SandboxProvider",
    "SandboxRegistry",
    "SandboxSession",
    "SandboxUnavailableError",
    "get_registry",
    "is_sandbox_enabled",
]
