"""Code-generated document formats: the model writes the builder, the worker runs it.

One folder per format (docx/pptx/xlsx/pdf) carries its `Office` spec and a
`SKILL.md` of authoring craft. `prompt.py` frames the request, `runner.py`
executes the returned code, and `render` below shapes the Built.
"""

import logging

from modules.llm.resolution import ResolvedGeneration
from worker.studio.office import prompt, runner
from worker.studio.office.spec import Office
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_text, slug

logger = logging.getLogger(__name__)

CODE_ATTEMPTS = 3


def render(
    spec: Office,
    model: ResolvedGeneration,
    sources: list[Source],
    user_prompt: str | None,
) -> Built:
    """Generate and run the code for one spec's format, then store its bytes."""
    fmt = spec.key
    system = prompt.build(spec, user_prompt)

    for attempt in range(CODE_ATTEMPTS):
        logger.info(
            "studio: office %s attempt %s/%s asking the model",
            fmt,
            attempt + 1,
            CODE_ATTEMPTS,
        )
        raw = generate.run_model(model, system, sources)
        try:
            logger.info(
                "studio: office %s attempt %s running %s chars of code",
                fmt,
                attempt + 1,
                len(raw),
            )
            namespace = runner.execute(runner.extract_code(raw))
            data = namespace.get("output_bytes")
            if not isinstance(data, bytes | bytearray):
                raise RuntimeError("generated code did not set `output_bytes` to bytes")
        except Exception as error:
            logger.info(
                "studio: office %s attempt %s failed: %s",
                fmt,
                attempt + 1,
                error,
            )
            if attempt == CODE_ATTEMPTS - 1:
                raise
            system = (
                f"{prompt.build(spec, user_prompt)}\n\n"
                f"Your previous script failed: {error}. Fix that and return "
                "only a corrected script."
            )
            continue

        title = as_text(namespace.get("title")) or (user_prompt or spec.label)[:200]
        summary = as_text(namespace.get("summary")) or f"# {title}"
        return Built(
            title=title,
            markdown=summary,
            primary=bytes(data),
            primary_mime=spec.mime,
            primary_filename=f"{slug(title, spec.stem)}.{spec.ext}",
        )
