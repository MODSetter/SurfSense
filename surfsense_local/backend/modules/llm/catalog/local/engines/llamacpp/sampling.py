"""The publisher's sampling for a curated chat model, as its entry commits it."""

from collections.abc import Sequence

from modules.llm.catalog.local.engines.llamacpp.manifest_fields import SamplingSet
from modules.llm.catalog.local.manifest import CuratedModel


def publisher_sampling(
    models: Sequence[CuratedModel], runtime_name: str, reasoning: bool | None
) -> SamplingSet | None:
    """The set for the mode the model answers in, or None to keep the runtime's
    defaults: a missing set is not filled from the other mode's."""
    entry = next(
        (
            model
            for model in models
            if any(b.runtime_name == runtime_name for b in model.as_builds())
        ),
        None,
    )
    if entry is None or entry.sampling is None:
        return None
    thinks = reasoning is not False and entry.template.reasoning is True
    return entry.sampling.thinking if thinks else entry.sampling.non_thinking
