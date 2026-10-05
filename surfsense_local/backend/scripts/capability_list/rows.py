"""The capability list's rows, written from ladder results."""

from pathlib import Path

from capability_list.ladder_input import LadderResults, ModelResults
from capability_list.verdict import verdict
from modules.llm.capability import AGENT_LEVELS, model_key
from modules.llm.capability.measured.schema import (
    SCHEMA_VERSION,
    CapabilityList,
    Match,
    MeasuredModel,
    Passes,
)

COMMITTED_INPUT = Path(__file__).with_name("ladder") / "create-and-edit-v1.json"


def measured_rows(results: LadderResults) -> CapabilityList:
    return CapabilityList(
        schema_version=SCHEMA_VERSION,
        provisional=results.provisional,
        source=results.source,
        models=[_row(results, model) for model in results.models],
    )


def _row(results: LadderResults, model: ModelResults) -> MeasuredModel:
    key = model_key(model.model_id)
    if key is None:
        raise ValueError(f"{model.model_id} is an alias, not a model to measure")
    found = verdict(model, results.cases)
    # A pass holds where it was measured; a failure everywhere, since a copy on
    # this computer is the same model or a smaller one.
    served = [model.served] if found.level in AGENT_LEVELS else ["remote", "local"]
    return MeasuredModel(
        key=key,
        match=Match(keys=[key, *model.also], served=served),
        level=found.level.value,
        suite=results.suite,
        suite_version=results.suite_version,
        measured_on=model.date,
        provider=model.provider,
        host=model.host,
        model_id=model.model_id,
        reads_images=model.reads_images,
        passes=Passes(passed=found.passed, counted=found.counted, run=found.run),
        note=model.note,
    )
