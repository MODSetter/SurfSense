"""Fold orchestrator-selected context into the single user message sent to a domain agent."""

from __future__ import annotations


def compose_child_task(task: str, *, curated_context: str | None = None) -> str:
    """Build the domain-agent user message: optional curated KB/context + task.

    When ``curated_context`` is set (from supervisor/KB wiring), it is prepended so the
    child sees only what orchestration chose — not the full parent transcript.
    """
    task = task.strip()
    if not curated_context or not curated_context.strip():
        return f"<delegated_task>\n{task}\n</delegated_task>"
    return (
        "<delegated_context>\n"
        f"{curated_context.strip()}\n"
        "</delegated_context>\n\n"
        "<delegated_task>\n"
        f"{task}\n"
        "</delegated_task>"
    )
