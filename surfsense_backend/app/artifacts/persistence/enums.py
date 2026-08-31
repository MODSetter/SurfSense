"""Artifact persistence enums."""

from enum import StrEnum


class ArtifactFileRole(StrEnum):
    PRIMARY = "primary"
    PREVIEW = "preview"


class ArtifactFormat(StrEnum):
    """Known artifact kinds. File-suffix inference may still store other strings."""

    MARKDOWN = "markdown"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    PDF = "pdf"
    MINDMAP = "mindmap"
    PODCAST = "podcast"
    VIDEO = "video"
    IMAGE = "image"
