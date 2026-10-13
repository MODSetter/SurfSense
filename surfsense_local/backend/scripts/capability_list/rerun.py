"""Fold a re-run's results into a screen, the way the committed screen was built by hand.

A person runs this on the two runs' `sweep-results.json` files and feeds the
folded screen to `catalog_rows.py`:

    python -c "
    from capability_list.rerun import folded
    from capability_list.sweep_input import SweepResults
    ...
    "
"""

from capability_list.sweep_input import AssumedModel, SweepResults, SweptModel
from capability_list.sweep_rows import CASE_CAP


def folded(base: SweepResults, rerun: SweepResults) -> SweepResults:
    """The screen with the re-run folded in.

    A re-run's verdict replaces the first one; a model the re-run left
    unfinished drops out; a model the re-run capped joins `assumed`.
    """
    models = {model.key: model for model in base.models}
    assumed = {model.key: model for model in base.assumed}
    for model in [*rerun.models, *rerun.unfinished]:
        if model.finished:
            models[model.key] = model
        else:
            models.pop(model.key, None)
            if _capped(model):
                assumed.setdefault(
                    model.key,
                    AssumedModel(
                        id=model.id, key=model.key, reads_images=model.reads_images
                    ),
                )
    # The sweep writes a capped model to `assumed` (level agent, status
    # done): its key is the re-run's verdict — out of models and
    # unfinished, into assumed.
    for model in rerun.assumed:
        models.pop(model.key, None)
        assumed[model.key] = model
    assumed_keys = {model.key for model in rerun.assumed}
    finished = {key for key, model in models.items() if model.finished}
    unfinished: dict[str, SweptModel] = {}
    for model in [*base.unfinished, *rerun.unfinished]:
        if model.key not in finished and model.key not in assumed_keys:
            unfinished.setdefault(model.key, model)
    return base.model_copy(
        update={
            "models": list(models.values()),
            "assumed": list(assumed.values()),
            "unfinished": list(unfinished.values()),
            "measured_on": rerun.measured_on or base.measured_on,
        }
    )


def _capped(model: SweptModel) -> bool:
    """Whether the re-run stopped it at the per-case dollar cap, unmeasured."""
    if model.notes is None:
        return False
    texts = [model.notes] if isinstance(model.notes, str) else model.notes
    return any(CASE_CAP in text for text in texts)
