"""Deterministic infographic prompt assembly."""

from __future__ import annotations

from collections.abc import Sequence

from .schemas import VisualStylePreset

_TASK = (
    "Create a polished, complete infographic from the supplied factual source. "
    "Choose the clearest visual hierarchy and composition. Summarize or omit "
    "secondary detail when necessary for readability. Keep all important content "
    "fully visible within the canvas, preserve factual accuracy, and follow the "
    "selected visual style."
)


def assemble_infographic_prompt(
    *,
    factual_content: str,
    style: VisualStylePreset,
    output_constraints: str | None = None,
    repair_findings: Sequence[str] = (),
) -> str:
    """Assemble factual content and the selected style into an image prompt."""
    if not factual_content.strip():
        raise ValueError("factual_content must not be empty")

    sections = [
        _TASK,
        f"CONTENT\n{factual_content}",
        f"VISUAL STYLE\n{style.description}",
    ]
    if output_constraints and output_constraints.strip():
        sections.append(f"OUTPUT CONSTRAINTS\n{output_constraints}")
    if repair_findings:
        sections.append(
            "REPAIR ALL OF THESE FINDINGS\n"
            + "\n".join(f"- {finding}" for finding in repair_findings)
        )
    return "\n\n".join(sections)


__all__ = ["assemble_infographic_prompt"]
