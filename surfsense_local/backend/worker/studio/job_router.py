"""The one place a format key meets its pipeline.

Every kind lives in its own folder and exposes `render(model, sources, prompt)`.
Adding a format is a new folder plus one `case` here; tests assert the enum
matches the API catalog (modules/artifacts/formats.py) key for key.
"""

import enum
from collections.abc import Callable
from functools import partial

from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.content.mindmap import pipeline as mindmap
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.content.summary import pipeline as summary
from worker.studio.media.audio.podcast import pipeline as podcast
from worker.studio.media.visual.image import pipeline as image
from worker.studio.media.visual.infographic import pipeline as infographic
from worker.studio.office import pipeline as office
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.office.pptx import pptx
from worker.studio.office.xlsx import xlsx
from worker.studio.shared.artifact import Built
from worker.studio.web.html import pipeline as html

Render = Callable[..., Built]


class Kind(enum.StrEnum):
    SUMMARY = "summary"
    MINDMAP = "mindmap"
    FLASHCARDS = "flashcards"
    QUIZ = "quiz"
    HTML = "html"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    PDF = "pdf"
    IMAGE = "image"
    INFOGRAPHIC = "infographic"
    PODCAST = "podcast"


def pipeline_for(kind: Kind) -> Render:
    match kind:
        case Kind.SUMMARY:
            return summary.render
        case Kind.MINDMAP:
            return mindmap.render
        case Kind.FLASHCARDS:
            return flashcards.render
        case Kind.QUIZ:
            return quiz.render
        case Kind.HTML:
            return html.render
        case Kind.DOCX:
            return partial(office.render, docx)
        case Kind.PPTX:
            return partial(office.render, pptx)
        case Kind.XLSX:
            return partial(office.render, xlsx)
        case Kind.PDF:
            return partial(office.render, pdf)
        case Kind.IMAGE:
            return image.render
        case Kind.INFOGRAPHIC:
            return infographic.render
        case Kind.PODCAST:
            return podcast.render
