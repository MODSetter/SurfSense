from worker.studio.builders.docx import docx
from worker.studio.builders.flashcards import flashcards
from worker.studio.builders.html_doc import html_doc
from worker.studio.builders.mindmap import mindmap
from worker.studio.builders.pdf import pdf
from worker.studio.builders.pptx import pptx
from worker.studio.builders.quiz import quiz
from worker.studio.builders.summary import summary
from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.xlsx import xlsx

# format key -> builder. Adding a format is a module and one line here; the
# API's dependency-free catalog (modules/artifacts/formats.py) must list the
# same keys, which tests/unit/worker/test_studio_builders.py asserts.
BUILDERS: dict[str, Builder] = {
    builder.key: builder
    for builder in (
        summary,
        docx,
        pptx,
        xlsx,
        html_doc,
        pdf,
        mindmap,
        flashcards,
        quiz,
    )
}

__all__ = ["BUILDERS", "Builder", "Built", "Source"]
