"""What a converted PDF was made from, kept in its metadata so a retry converts the same file."""

from dataclasses import dataclass
from typing import Any

CONVERSION_KEY = "conversion"
# What LibreOffice converts here: the Word files and decks the agent makes, and
# sources of the same kinds.
CONVERTIBLE_SUFFIXES = (".docx", ".pptx")


@dataclass(frozen=True)
class Conversion:
    """Exactly one of an artifact version and a source; either file is only read."""

    artifact_id: int | None = None
    document_id: int | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {"artifact_id": self.artifact_id, "document_id": self.document_id}


def conversion_of(metadata: dict[str, Any] | None) -> Conversion | None:
    found = (metadata or {}).get(CONVERSION_KEY)
    if not isinstance(found, dict):
        return None
    return Conversion(found.get("artifact_id"), found.get("document_id"))
