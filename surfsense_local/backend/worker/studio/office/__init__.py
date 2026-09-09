"""Code-generated document formats: the model writes the builder, the worker runs it.

One folder per format (docx/pptx/xlsx/pdf) carries its `Office` spec and a
`SKILL.md` of authoring craft. `prompt.py` frames the request, `runner.py`
executes the returned code, and `render` below shapes the Built.
"""

import logging

from sqlalchemy.orm import Session

from worker.studio import generate
from worker.studio.artifact import Built, Source
from worker.studio.office import prompt, runner
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.office.pptx import pptx
from worker.studio.office.spec import Office
from worker.studio.office.xlsx import xlsx
from worker.studio.text import as_text, slug

logger = logging.getLogger(__name__)

# format key -> spec. The pipeline routes these keys here instead of to BUILDERS.
OFFICE: dict[str, Office] = {spec.key: spec for spec in (docx, pptx, xlsx, pdf)}

CODE_ATTEMPTS = 3


def render(
    session: Session, fmt: str, sources: list[Source], user_prompt: str | None
) -> Built:
    """Generate and run the code for one picked format, then store its bytes."""
    spec = OFFICE[fmt]
    system = prompt.build(spec, user_prompt)

    for attempt in range(CODE_ATTEMPTS):
        logger.info(
            "studio: office %s attempt %s/%s asking the model",
            fmt,
            attempt + 1,
            CODE_ATTEMPTS,
        )
        raw = generate.run_model(session, system, sources)
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
                raise RuntimeError(
                    "generated code did not set `output_bytes` to bytes"
                )
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


__all__ = ["OFFICE", "Office", "render"]
