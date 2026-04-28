"""Architecture mode contracts and resolution helpers for chat sessions."""

from __future__ import annotations

from enum import StrEnum

from app.config import config


class ArchitectureMode(StrEnum):
    SINGLE_AGENT = "single_agent"
    SHADOW_MULTI_AGENT_V1 = "shadow_multi_agent_v1"
    MULTI_AGENT_V1 = "multi_agent_v1"


def parse_architecture_mode(value: str | None) -> ArchitectureMode | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    try:
        return ArchitectureMode(normalized)
    except ValueError:
        return None


def resolve_architecture_mode(request_override: str | None = None) -> ArchitectureMode:
    if config.FORCE_SINGLE_AGENT:
        return ArchitectureMode.SINGLE_AGENT

    override_mode = parse_architecture_mode(request_override)
    if override_mode is not None:
        return override_mode

    default_mode = parse_architecture_mode(config.AGENT_ARCHITECTURE_MODE)
    if default_mode is not None:
        return default_mode

    return ArchitectureMode.SINGLE_AGENT
