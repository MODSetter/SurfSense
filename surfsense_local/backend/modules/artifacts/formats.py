from collections.abc import Callable
from dataclasses import dataclass

from modules.artifacts.podcast import brief


@dataclass(frozen=True)
class Format:
    """One Studio deliverable the app can produce."""

    key: str
    label: str
    # In the order the pipeline's render() takes its models.
    requires_roles: tuple[str, ...] = ("generation",)
    # ponytail: the voice engine is not a selectable role yet, so it is a flag;
    # it folds into requires_roles when a text_to_speech role exists.
    requires_voice: bool = False
    # Checks and fills the request's options, or raises ValueError with why.
    # Formats without one take no options.
    validate_options: Callable[[dict | None], dict] | None = None


# worker/studio/job_router.py must name every key here and nothing else
# (asserted in tests/unit/worker).
FORMATS: tuple[Format, ...] = (
    Format("summary", "Summary"),
    Format("docx", "Document"),
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
        requires_voice=True,
        validate_options=brief.validate_options,
    ),
    Format("image", "Image", requires_roles=("image_generation", "generation")),
    Format(
        "infographic", "Infographic", requires_roles=("image_generation", "generation")
    ),
)

FORMATS_BY_KEY: dict[str, Format] = {fmt.key: fmt for fmt in FORMATS}
