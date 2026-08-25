"""HTTPS username/password for ``engine.push``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteCredentials:
    """Ephemeral git HTTP auth. Never persist, never return over HTTP."""

    username: str
    password: str
