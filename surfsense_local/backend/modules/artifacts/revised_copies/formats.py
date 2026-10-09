"""The files SurfSense revises, by suffix: the artifact format each becomes and its media type."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RevisableFormat:
    format: str  # the artifact's format, which picks its engine and viewer
    suffix: str  # kept on the revised copy, so a macro workbook stays one
    mime: str


_FORMATS = (
    RevisableFormat(
        "docx",
        ".docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    RevisableFormat(
        "xlsx",
        ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    RevisableFormat("xlsx", ".xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12"),
    RevisableFormat(
        "pptx",
        ".pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
)
REVISABLE: dict[str, RevisableFormat] = {f.suffix: f for f in _FORMATS}

SUFFIXES_SENTENCE = "SurfSense revises .docx, .xlsx, .xlsm and .pptx files."


def revisable_format(name: str | Path) -> RevisableFormat | None:
    return REVISABLE.get(Path(name).suffix.lower())
