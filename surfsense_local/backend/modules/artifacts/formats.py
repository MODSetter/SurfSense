from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    """One Studio deliverable the app can produce."""

    key: str
    label: str
    requires_role: str | None = "generation"


# The whole Studio catalog. Kept dependency-free so the API validates and lists
# without importing the builder libraries; the worker's BUILDERS registry must
# carry a builder for every non-visual key (asserted in the worker unit test).
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
    Format("podcast", "Podcast"),
    Format("image", "Image", requires_role="image_generation"),
    Format("infographic", "Infographic"),
)

FORMATS_BY_KEY: dict[str, Format] = {fmt.key: fmt for fmt in FORMATS}
