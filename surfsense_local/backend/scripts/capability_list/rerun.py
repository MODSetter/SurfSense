"""Fold a re-run's results into a screen, on parsed results.

`folded` is the fold itself. To fold a re-run into the committed
screen, run `scripts/fold_screen.py`: it applies the same rules at the
JSON level, because a Pydantic round-trip drops the provenance extras
the committed screen carries.
"""

from capability_list.sweep_input import SweepResults, SweptModel


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
            # A measured verdict replaces the assumption: no stale row
            # beside the measured result.
            assumed.pop(model.key, None)
        else:
            # No verdict: the model drops out, and a stale assumption
            # goes with it, as a measured verdict clears one.
            models.pop(model.key, None)
            assumed.pop(model.key, None)
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

