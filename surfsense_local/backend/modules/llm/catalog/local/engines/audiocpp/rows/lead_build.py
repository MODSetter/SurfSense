"""The build an audio row leads with: in use, else installed, else the default."""

from collections.abc import Sequence

from modules.llm.catalog.local.rows import BuildRow, Lead, LeadReason


def lead_build(
    builds: Sequence[BuildRow],
    default_quantization: str | None,
    *,
    selected: str | None,
) -> Lead | None:
    for row in builds:
        if selected is not None and row.installed_as == selected:
            return Lead(row.build.quantization, LeadReason.IN_USE)
    for row in builds:
        if row.installed_as:
            return Lead(row.build.quantization, LeadReason.INSTALLED)
    for row in builds:
        if row.build.quantization == default_quantization:
            return Lead(row.build.quantization, LeadReason.DEFAULT)
    return None
