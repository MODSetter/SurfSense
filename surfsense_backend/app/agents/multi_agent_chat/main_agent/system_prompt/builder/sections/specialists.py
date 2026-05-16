"""``<specialists>`` section — live ``task`` roster for this workspace.

The roster is non-empty by contract: ``deliverables`` and ``knowledge_base``
both declare ``frozenset()`` in ``SUBAGENT_TO_REQUIRED_CONNECTOR_MAP``, so
they survive every connector-based exclusion pass.
"""

from __future__ import annotations


def build_specialists_section(
    specialist_lines: list[tuple[str, str]],
) -> str:
    bullets = "\n".join(f"- **{name}** — {desc}" for name, desc in specialist_lines)
    return f"\n<specialists>\n{bullets}\n</specialists>\n"
