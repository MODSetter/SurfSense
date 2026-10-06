"""The capability a selection reports, with the opt-in it is offered."""

from modules.llm.capability.agent_gate import gate_block, remote_facts
from modules.llm.capability.agent_trial import agent_trial
from modules.llm.capability.level import Level
from modules.llm.capability.measured.loader import measured_list
from modules.llm.capability.resolve import capability_of
from modules.llm.capability.schemas import (
    AgentTrialRead,
    CapabilityRead,
    MeasuredRead,
    ReasonRead,
)
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp

__all__ = ["capability_read", "trial_block"]


def capability_read(
    selected: SelectedModel, catalog_provider: str | None
) -> CapabilityRead:
    """Synchronous and offline, so every selection read can carry it."""
    capability = capability_of(selected.name, selected.connection)
    row = capability.row
    held = row is not None and capability.level is not Level.NOT_MEASURED
    blocked = trial_block(selected, catalog_provider)
    offered = capability.level is Level.NOT_MEASURED and blocked is None
    return CapabilityRead(
        level=capability.level,
        label_key=capability.level.value,
        reason=ReasonRead(code=capability.reason.code, values=capability.reason.values),
        note=row.note if held else None,
        measured=MeasuredRead(
            key=row.key,
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
        agent_trial=AgentTrialRead(
            offered=offered,
            enabled=offered and agent_trial(selected),
            blocked=blocked if capability.level is Level.NOT_MEASURED else None,
        ),
    )


def trial_block(selected: SelectedModel, catalog_provider: str | None) -> str | None:
    """Why the opt-in cannot be offered, as far as the catalog tells without a call.

    A local model's tool calls and window are read when a chat starts: asking
    llama-server here would load the model on every read.
    """
    if selected.provider == llamacpp.PROVIDER:
        return None
    return gate_block(remote_facts(selected.name, catalog_provider), measured=False)
