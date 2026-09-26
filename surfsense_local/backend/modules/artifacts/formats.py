from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.artifacts.podcast import brief
from modules.llm.model_type import ModelType


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


# worker/studio/job_router.py must name every key here and nothing else
# (asserted in tests/unit/worker).
FORMATS: tuple[Format, ...] = (
    Format("summary", "Summary"),
    Format("docx", "Word"),
    Format("pptx", "Slides"),
    Format("xlsx", "Spreadsheet"),
    Format("html", "Web page"),
    Format("pdf", "PDF"),
    Format("mindmap", "Mind map"),
    Format("flashcards", "Flashcards"),
    Format("quiz", "Quiz"),
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
