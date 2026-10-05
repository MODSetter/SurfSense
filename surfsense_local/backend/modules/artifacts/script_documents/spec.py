"""The spec an artifact keeps: the source an edit changes and a run renders again."""

from dataclasses import dataclass
from typing import Any, Literal, get_args

DocumentFormat = Literal["docx", "pdf", "pptx", "xlsx"]
SpecKind = Literal["python", "markdown"]

DOCUMENT_FORMATS: tuple[DocumentFormat, ...] = get_args(DocumentFormat)

# What each format is called in a sentence the agent reads.
FORMAT_NAMES: dict[str, str] = {
    "docx": "Word document",
    "pdf": "PDF",
    "pptx": "PowerPoint deck",
    "xlsx": "Excel workbook",
}


@dataclass(frozen=True)
class DocumentScript:
    """Python that writes one file of its format to OUTPUT_PATH from the named images.

    `template_source_id` names a source whose original file the run copies to
    TEMPLATE_PATH; the next version keeps it unless its call names another.
    """

    text: str
    format: DocumentFormat
    images: tuple[str, ...]
    template_source_id: int | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "kind": "python",
            "text": self.text,
            "format": self.format,
            "images": list(self.images),
            "template_source_id": self.template_source_id,
        }


def spec_kind(metadata: dict[str, Any] | None) -> SpecKind | None:
    """The kind of spec an artifact keeps; None when Studio drafted it and kept none."""
    spec = (metadata or {}).get("spec")
    kind = spec.get("kind") if isinstance(spec, dict) else None
    return kind if kind in get_args(SpecKind) else None


def document_script(metadata: dict[str, Any] | None) -> DocumentScript | None:
    """The script an artifact was made from, or None for any other artifact."""
    if spec_kind(metadata) != "python":
        return None
    spec = metadata["spec"]
    return DocumentScript(
        text=spec["text"],
        format=spec["format"],
        images=tuple(spec["images"]),
        # Absent from versions made before templates existed.
        template_source_id=spec.get("template_source_id"),
    )
