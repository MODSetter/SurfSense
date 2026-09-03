"""Deterministic infographic prompt assembly."""

from __future__ import annotations

from collections.abc import Sequence

from .schemas import VisualStylePreset

MAX_FACTUAL_CONTENT_CHARS = 16_000
MAX_REPAIR_FINDINGS = 20
MAX_REPAIR_FINDING_CHARS = 500

_TASK = (
    "Create one complete infographic, not a decorative standalone scene. "
    "Preserve every supplied fact, number, label, relationship, and ordering."
)
_LEGIBILITY = (
    "Use a clear reading direction, strong hierarchy, generous spacing, high "
    "contrast, short readable labels, and no paragraph-sized text."
)
_OUTPUT = (
    "Use one fully composed canvas. Do not crop content or add mockup frames, "
    "watermarks, unexplained branding, duplicated sections, invented facts, "
    "placeholder copy, or UI chrome."
)


def _bounded(value: str, *, field: str, maximum: int) -> str:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} is too long")
    return value


def assemble_infographic_prompt(
    *,
    factual_content: str,
    style: VisualStylePreset,
    output_constraints: str | None = None,
    repair_findings: Sequence[str] = (),
) -> str:
    """Append the preset description unchanged to a bounded factual prompt."""
    facts = _bounded(
        factual_content,
        field="factual_content",
        maximum=MAX_FACTUAL_CONTENT_CHARS,
    )
    if len(repair_findings) > MAX_REPAIR_FINDINGS:
        raise ValueError("too many repair findings")
    findings = [
        _bounded(
            finding,
            field=f"repair_findings.{index}",
            maximum=MAX_REPAIR_FINDING_CHARS,
        )
        for index, finding in enumerate(repair_findings)
    ]

    sections = [
        _TASK,
        f"CONTENT\n{facts}",
        f"VISUAL STYLE\n{style.description}",
        _LEGIBILITY,
        _OUTPUT,
    ]
    if output_constraints and output_constraints.strip():
        sections.append(
            "OUTPUT CONSTRAINTS\n"
            + _bounded(
                output_constraints,
                field="output_constraints",
                maximum=2_000,
            )
        )
    if findings:
        sections.append(
            "REPAIR ALL OF THESE FINDINGS\n"
            + "\n".join(f"- {finding}" for finding in findings)
        )
    return "\n\n".join(sections)


__all__ = ["assemble_infographic_prompt"]
