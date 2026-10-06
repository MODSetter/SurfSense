"""Studio's PowerPoint and Excel: the model writes a script, the script runner runs it.

One folder per format (docx/pptx/xlsx/pdf) carries its `Office` spec and a
`SKILL.md` of authoring craft. `prompt.py` frames the request; the script saves
to OUTPUT_PATH in its own process (ADR 0039), never in the worker's.
"""

import logging

from modules.artifacts.script_documents.spec import DocumentScript
from modules.llm.resolution import ResolvedGeneration
from shared import cancellation
from worker.studio.office import prompt
from worker.studio.office.document.reply import script_reply, script_title
from worker.studio.office.document.script_path import (
    REPAIR_CHARS,
    StudioScriptFailedError,
)
from worker.studio.office.spec import Office
from worker.studio.script_document import pipeline as script_document
from worker.studio.script_document.pipeline import ScriptRunFailedError
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, fallback_title

logger = logging.getLogger(__name__)

CODE_ATTEMPTS = 3


def render(
    spec: Office,
    model: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    """Ask for the format's script and run it, showing a failure back to the model."""
    fmt = spec.key
    system = prompt.build(model.tier, spec, user_prompt)
    fallback = fallback_title(user_prompt, sources, spec.label)
    repair: generate.Repair | None = None

    for attempt in range(CODE_ATTEMPTS):
        # Outside the try below: a cancel must not be mistaken for broken code.
        cancellation.raise_if_cancelled()
        logger.info(
            "studio: office %s attempt %s/%s asking the model",
            fmt,
            attempt + 1,
            CODE_ATTEMPTS,
        )
        raw = generate.run_model(model, system, sources, repair=repair)
        try:
            return _run(spec, script_reply(raw), fallback)
        except StudioScriptFailedError as error:
            logger.info(
                "studio: office %s attempt %s failed: %s", fmt, attempt + 1, error
            )
            if attempt == CODE_ATTEMPTS - 1:
                raise
            repair = generate.Repair(
                reply=raw,
                instruction=(
                    f"That script failed: {error.shown}. Return the whole script "
                    "corrected, changing only what the error points to."
                ),
            )
    raise AssertionError("unreachable")  # pragma: no cover


def _run(spec: Office, script: str, fallback: str) -> Built:
    """No spec is kept: a deck or workbook Studio drafts has no versions to edit."""
    if not script:
        raise StudioScriptFailedError("the model returned no script")
    stored = DocumentScript(text=script, format=spec.key, images=())
    try:
        return script_document.render(script_title(script) or fallback, stored, {})
    except ScriptRunFailedError as error:
        raise StudioScriptFailedError(
            error.error, error.reason(REPAIR_CHARS)
        ) from error
