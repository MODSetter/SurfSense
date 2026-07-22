"""Register a recorded scraper run as a citable ``[n]``."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)


def attach_run_citation(
    registry: CitationRegistry,
    *,
    run_external_id: str,
    capability: str,
) -> tuple[int, str]:
    """Register the ``run_<uuid>`` handle; return its ``[n]`` and the label line."""
    n = registry.register(
        CitationSourceType.RUN,
        {"run_id": run_external_id},
        {"capability": capability},
    )
    return n, f"\n\nCite this scraper run as [{n}] after any claim drawn from its data."
