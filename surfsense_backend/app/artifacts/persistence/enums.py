"""Artifact persistence enums."""

from enum import StrEnum


class ArtifactFileRole(StrEnum):
    PRIMARY = "primary"
    PREVIEW = "preview"
    SOURCE = "source"
