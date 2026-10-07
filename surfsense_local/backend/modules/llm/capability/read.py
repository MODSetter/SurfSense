"""The capability a selection reports, with the modes a new chat on it may take."""

from modules.llm.capability.agent_gate import catalog_facts
from modules.llm.capability.level import Level
from modules.llm.capability.measured.loader import measured_list
from modules.llm.capability.modes import new_chat_modes
from modules.llm.capability.resolve import capability_of
from modules.llm.capability.schemas import (
    CapabilityRead,
    MeasuredRead,
    ModesRead,
    ReasonRead,
)
from modules.llm.models import SelectedModel

__all__ = ["capability_read"]


def capability_read(
    selected: SelectedModel, catalog_provider: str | None
) -> CapabilityRead:
    """Synchronous and offline, so every selection read can carry it."""
    capability = capability_of(selected.name, selected.connection)
    row = capability.row
    held = row is not None and capability.level is not Level.NOT_MEASURED
    modes = new_chat_modes(selected, catalog_facts(selected, catalog_provider))
    return CapabilityRead(
        level=capability.level,
        label_key=capability.level.value,
        reason=ReasonRead(code=capability.reason.code, values=capability.reason.values),
        note=row.note if held else None,
        measured=MeasuredRead(
            key=row.key,
            suite=row.suite,
            assumed=row.assumed,
            suite_version=row.suite_version,
            measured_on=row.measured_on.isoformat(),
            provider=row.provider,
            host=row.host,
            reads_images=row.reads_images,
            passed=row.passes.passed,
            counted=row.passes.counted,
            provisional=measured_list().provisional,
        )
        if held
        else None,
        modes=ModesRead(
            agentic_allowed=modes.agentic_allowed,
            blocked=modes.blocked,
            default_mode=modes.default_mode,
            reason=ReasonRead(code=modes.reason.code, values=modes.reason.values),
            remembered_mode=modes.remembered_mode,
        ),
    )
