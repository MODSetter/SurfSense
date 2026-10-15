from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from modules.artifacts.podcast import brief
from modules.llm.model_type import ModelType


class Grounding(StrEnum):
    """How a selection larger than the budget is cut down for a format."""

    # The passages that best match the user's prompt, from every document.
    PASSAGES = "passages"
    # Each document from its start: the format reads a document's shape.
    WHOLE = "whole"


@dataclass(frozen=True)
class Format:
    """One Studio deliverable the app can produce."""

    key: str
    label: str
    # In the order the pipeline's render() takes its models.
    requires_model_types: tuple[ModelType, ...] = (ModelType.TEXT_GEN,)
    # Checks and fills the request's options, or raises ValueError with why.
    # Formats without one take no options.
    validate_options: Callable[[Session, dict | None], dict] | None = None
    grounding: Grounding = Grounding.PASSAGES
    # What to search a selection too big to share for, when no prompt says.
    default_focus: str = "the main points, findings, figures and conclusions"


# worker/studio/job_router.py must name every key here and nothing else
# (asserted in tests/unit/worker).
FORMATS: tuple[Format, ...] = (
    Format("summary", "Markdown", grounding=Grounding.WHOLE),
    Format("docx", "Word"),
    Format("pptx", "Slides"),
    Format("xlsx", "Spreadsheet"),
    Format("html", "Web page"),
    Format("pdf", "PDF"),
    Format("mindmap", "Mind map", grounding=Grounding.WHOLE),
    Format(
        "flashcards",
        "Flashcards",
        default_focus="key terms, definitions, facts and figures",
    ),
    Format("quiz", "Quiz", default_focus="key facts, definitions, figures and causes"),
    Format(
        "podcast",
        "Podcast",
        requires_model_types=(ModelType.TEXT_GEN, ModelType.AUDIO_GEN),
        validate_options=brief.validate_options,
    ),
    Format(
        "image",
        "Image",
        requires_model_types=(ModelType.IMAGE_GEN, ModelType.TEXT_GEN),
    ),
    Format(
        "infographic",
        "Infographic",
        requires_model_types=(ModelType.IMAGE_GEN, ModelType.TEXT_GEN),
    ),
)

FORMATS_BY_KEY: dict[str, Format] = {fmt.key: fmt for fmt in FORMATS}
