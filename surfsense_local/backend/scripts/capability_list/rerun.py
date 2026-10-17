"""Fold a re-run's results into a screen, the way the committed screen was built by hand.

A person runs this on the two runs' `sweep-results.json` files and feeds the
folded screen to `catalog_rows.py`:

    PYTHONPATH=scripts uv run python -c "
    from pathlib import Path
    from capability_list.rerun import folded
    from capability_list.sweep_input import SweepResults
    base = SweepResults.model_validate_json(Path('scripts/capability_list/sweep/openrouter-screen-v1.json').read_text())
    rerun = SweepResults.model_validate_json(Path('<rerun>/sweep-results.json').read_text())
    Path('/tmp/folded-screen.json').write_text(folded(base, rerun).model_dump_json(indent=2))
    "

Run from surfsense_local/backend; `<rerun>` is the
re-run's --out folder. The folded file is not the screen to commit as-is:
a Pydantic round-trip drops the provenance extras the committed screen
carries, so merge its verdicts into the committed screen at the JSON
level and commit that.
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

