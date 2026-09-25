"""A curated chat model as the eval runs it, read from the local manifest."""

from dataclasses import dataclass

from modules.llm.catalog.local.engines.llamacpp.builds.choice import default_build
from modules.llm.catalog.local.manifest.loader import load_local_manifest
from modules.llm.profile import Tier, classify, from_name


@dataclass(frozen=True)
class EvalModel:
    id: str
    # The default build once installed, as llama-server's router lists it.
    local_name: str
    # Featherless lists a model by its source repo.
    featherless_name: str
    # The app's tier for the local build, on both targets.
    tier: Tier
    sampling: dict[str, float | int]


def eval_model(model_id: str) -> EvalModel:
    """Every machine runs the default build, not the one it would recommend."""
    entry = next((m for m in load_local_manifest().models if m.id == model_id), None)
    if entry is None or entry.sampling is None:
        raise ValueError(f"{model_id} is not a curated chat model")
    build = default_build(entry.as_builds())
    # A hybrid model's answers think, so its thinking set; Gemma 3 has only the other.
    chosen = entry.sampling.thinking or entry.sampling.non_thinking
    return EvalModel(
        id=entry.id,
        local_name=build.runtime_name,
        featherless_name=entry.source_repo,
        tier=classify(from_name("llamacpp", build.runtime_name)),
        sampling=chosen.model_dump(exclude_none=True) if chosen else {},
    )
