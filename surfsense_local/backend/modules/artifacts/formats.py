from dataclasses import dataclass


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


# The whole Studio catalog. Kept dependency-free so the API validates and lists
# without importing the render libraries; worker/studio/job_router.py must name
# every key here and nothing else (asserted in tests/unit/worker).
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
    Format("podcast", "Podcast", requires_voice=True),
    Format("image", "Image", requires_roles=("image_generation",)),
    Format(
        "infographic", "Infographic", requires_roles=("image_generation", "generation")
    ),
)

FORMATS_BY_KEY: dict[str, Format] = {fmt.key: fmt for fmt in FORMATS}
