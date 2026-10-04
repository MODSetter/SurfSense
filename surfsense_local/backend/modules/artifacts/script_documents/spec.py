"""The spec an artifact keeps: the source an edit changes and a run renders again."""

from dataclasses import dataclass
from typing import Any, Literal, get_args

DocumentFormat = Literal["docx", "pdf"]
SpecKind = Literal["python", "markdown"]

DOCUMENT_FORMATS: tuple[DocumentFormat, ...] = get_args(DocumentFormat)


@dataclass(frozen=True)
class DocumentScript:
    """Python that writes one Word or PDF file to OUTPUT_PATH from the named images."""

    text: str
    format: DocumentFormat
    images: tuple[str, ...]

    def as_metadata(self) -> dict[str, Any]:
        return {
            "kind": "python",
            "text": self.text,
            "format": self.format,
            "images": list(self.images),
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
        text=spec["text"], format=spec["format"], images=tuple(spec["images"])
    )
