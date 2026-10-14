"""The one loop every Studio script format drafts in: ask, run, show a failure back."""

from collections.abc import Callable

from modules.llm.resolution import ResolvedGeneration
from shared import cancellation
from worker.studio.office.script_failed import StudioScriptFailedError
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source

# A script that fails is shown its error twice before the job gives up.
ATTEMPTS = 3


def drafted(
    model: ResolvedGeneration,
    system: str,
    sources: list[Source],
    run: Callable[[str], Built],
) -> Built:
    """`run` turns the model's reply into the built file, or raises
    StudioScriptFailedError with what the model is shown to fix it."""
    repair: generate.Repair | None = None
    for attempt in range(ATTEMPTS):
        # Outside the try below: a cancel must not be mistaken for a broken script.
        cancellation.raise_if_cancelled()
        raw = generate.run_model(model, system, sources, repair=repair)
        try:
            return run(raw)
        except StudioScriptFailedError as error:
            if attempt == ATTEMPTS - 1:
                raise
            repair = generate.Repair(
                reply=raw,
                instruction=(
                    f"That script failed: {error.shown}. Return the whole script "
                    "corrected, changing only what the error points to."
                ),
            )
    raise AssertionError("unreachable")  # pragma: no cover
