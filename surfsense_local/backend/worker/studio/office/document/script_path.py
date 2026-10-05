"""A strong model's path: it writes a script, which runs in the runner, not in exec()."""

import re
from collections.abc import Iterable
from dataclasses import replace
from importlib.resources import files

from modules.artifacts.script_documents.spec import DocumentScript, DocumentSpec
from modules.llm import prompting
from modules.llm.resolution import ResolvedGeneration
from shared import cancellation
from worker.studio.office.document.figure_list import script_figures
from worker.studio.office.document.figure_shelf import shelf_of
from worker.studio.office.document.reply import (
    first_heading,
    script_reply,
    script_title,
)
from worker.studio.office.spec import Office
from worker.studio.script_document import pipeline as script_document
from worker.studio.script_document.pipeline import ScriptRunFailedError
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, SourceImage, fallback_title
from worker.studio.shared.text import file_stem

# A draft's script that fails is shown its error twice before the job gives up.
ATTEMPTS = 3
# What of a failure the model is shown to fix it: the error and the traceback's end.
REPAIR_CHARS = 2000


class StudioScriptFailedError(RuntimeError):
    """Studio's script failed; Retry asks the model again, so no "Script error:" mark."""

    def __init__(self, error: str, shown: str | None = None) -> None:
        super().__init__(f"The document script failed: {error}")
        # The error and the traceback's end, as the model is shown them to fix it.
        self.shown = shown or error


def draft(
    office: Office,
    model: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    figures = shelf_of(sources)
    system = prompting.load(
        __package__,
        model.tier,
        case="script",
        label=office.label,
        library=office.library,
        rules=rules(office),
        focus=prompting.focus(user_prompt),
        figures=script_figures(figures),
    )
    title = fallback_title(user_prompt, sources, office.label)
    repair: generate.Repair | None = None
    for attempt in range(ATTEMPTS):
        # Outside the try below: a cancel must not be mistaken for a broken script.
        cancellation.raise_if_cancelled()
        raw = generate.run_model(model, system, sources, repair=repair)
        try:
            return run(office, script_reply(raw), figures, title)
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


def run(
    office: Office, script: str, figures: Iterable[SourceImage], title: str
) -> Built:
    """Run the script with the figures it names, keeping it as the version's spec."""
    if not script:
        raise StudioScriptFailedError("the model returned no script")
    images = {
        figure.name: figure.path for figure in figures if _names(script, figure.name)
    }
    title = script_title(script) or title
    stored = DocumentScript(text=script, format=office.key, images=tuple(images))
    try:
        built = script_document.render(title, stored, images)
    except ScriptRunFailedError as error:
        raise StudioScriptFailedError(
            error.error, error.reason(REPAIR_CHARS)
        ) from error
    if script_title(script) is None and (heading := first_heading(built.markdown)):
        built = replace(
            built,
            title=heading,
            primary_filename=f"{file_stem(heading, office.stem)}.{office.ext}",
        )
    spec = DocumentSpec("python", script, office.key, tuple(images))
    return replace(built, spec=spec.as_metadata())


def rules(office: Office) -> str:
    """The format's authoring rules for a script that saves to OUTPUT_PATH."""
    return (
        (files(__package__) / "rules" / f"{office.key}.md").read_text("utf-8").strip()
    )


def _names(script: str, name: str) -> bool:
    """Whether the script names the figure: "12-1" is not inside "12-10" or "112-1"."""
    return re.search(rf"(?<![0-9-]){re.escape(name)}(?![0-9])", script) is not None
