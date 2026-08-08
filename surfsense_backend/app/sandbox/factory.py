"""Provider selection.

`SANDBOX_PROVIDER` is a deployment choice, not a fallback chain: an
unreachable provider is an error to fix, never a reason to silently run
somewhere else.
"""

from __future__ import annotations

from app.config import config as app_config

from .protocol import SandboxProvider

_PROVIDERS = ("opensandbox", "daytona")


def is_sandbox_enabled() -> bool:
    """Whether code execution is available at all, whichever provider is set."""
    return app_config.SANDBOX_ENABLED


def build_provider() -> SandboxProvider:
    name = app_config.SANDBOX_PROVIDER
    # Imported lazily so a deployment only needs the SDK it actually uses.
    if name == "opensandbox":
        from .providers.opensandbox import OpenSandboxProvider

        return OpenSandboxProvider()
    if name == "daytona":
        from .providers.daytona import DaytonaProvider

        return DaytonaProvider()
    raise ValueError(
        f"Unknown SANDBOX_PROVIDER {name!r}. Expected one of: {', '.join(_PROVIDERS)}"
    )
