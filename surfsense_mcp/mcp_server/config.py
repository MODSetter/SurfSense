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
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8080


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for a server process."""

    base_url: str
    api_key: str | None
    api_prefix: str
    timeout: float
    default_workspace: str | None
    host: str
    port: int

    @property
    def api_base(self) -> str:
        return f"{self.base_url}{self.api_prefix}"

    @classmethod
    def from_env(cls) -> Settings:
        # Optional here: remote (http) callers pass their own key per request in
        # a header. ``__main__`` enforces it for stdio, its only source of a key.
        api_key = os.environ.get("SURFSENSE_API_KEY", "").strip() or None

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

        host = os.environ.get("SURFSENSE_MCP_HOST", "").strip() or DEFAULT_HTTP_HOST
        raw_port = os.environ.get("SURFSENSE_MCP_PORT", "").strip()
        try:
            port = int(raw_port) if raw_port else DEFAULT_HTTP_PORT
        except ValueError:
            port = DEFAULT_HTTP_PORT

        return cls(
            base_url=base_url,
            api_key=api_key,
            api_prefix=api_prefix,
            timeout=timeout,
            default_workspace=default_workspace,
            host=host,
            port=port,
        )
