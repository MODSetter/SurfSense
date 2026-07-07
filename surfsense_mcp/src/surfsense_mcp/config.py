"""Runtime configuration, read once from the environment.

Secrets never live in code or client config files — the client (Cursor/Claude)
passes them as environment variables when it launches this server (see README).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for a server process."""

    base_url: str
    api_key: str
    api_prefix: str
    timeout: float
    default_workspace: str | None

    @property
    def api_base(self) -> str:
        return f"{self.base_url}{self.api_prefix}"

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.environ.get("SURFSENSE_API_KEY", "").strip()
        if not api_key:
            raise SystemExit(
                "SURFSENSE_API_KEY is required. Create an API key in SurfSense "
                "(Settings -> API) and pass it via the SURFSENSE_API_KEY "
                "environment variable."
            )

        base_url = (
            os.environ.get("SURFSENSE_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        )
        api_prefix = "/" + os.environ.get(
            "SURFSENSE_API_PREFIX", DEFAULT_API_PREFIX
        ).strip().strip("/")

        raw_timeout = os.environ.get("SURFSENSE_TIMEOUT", "").strip()
        try:
            timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT_SECONDS
        except ValueError:
            timeout = DEFAULT_TIMEOUT_SECONDS

        default_workspace = os.environ.get("SURFSENSE_WORKSPACE", "").strip() or None

        return cls(
            base_url=base_url,
            api_key=api_key,
            api_prefix=api_prefix,
            timeout=timeout,
            default_workspace=default_workspace,
        )
