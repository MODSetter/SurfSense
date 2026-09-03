"""Closed contracts for trusted infographic visual-style presets."""

from __future__ import annotations

import re
from dataclasses import dataclass

PRESET_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
MAX_PRESET_ID_CHARS = 64
MAX_PRESET_LABEL_CHARS = 80
MAX_PRESET_DESCRIPTION_CHARS = 600
MAX_PREVIEW_ASSET_CHARS = 120


def _bounded_text(value: str, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} is too long")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError(f"{field} contains unsupported control characters")
    return value


def _preset_id(value: str, *, field: str = "id") -> str:
    value = _bounded_text(value, field=field, maximum=MAX_PRESET_ID_CHARS)
    if PRESET_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase slug")
    return value


@dataclass(frozen=True, slots=True)
class VisualStylePreset:
    """One immutable concrete style description sent to an image model."""

    id: str
    version: int
    label: str
    preview_asset: str
    description: str

    def __post_init__(self) -> None:
        _preset_id(self.id)
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version <= 0
        ):
            raise ValueError("version must be a positive integer")
        _bounded_text(self.label, field="label", maximum=MAX_PRESET_LABEL_CHARS)
        preview_asset = _bounded_text(
            self.preview_asset,
            field="preview_asset",
            maximum=MAX_PREVIEW_ASSET_CHARS,
        )
        if not preview_asset.startswith("infographic-style/"):
            raise ValueError("preview_asset must use the infographic-style namespace")
        _bounded_text(
            self.description,
            field="description",
            maximum=MAX_PRESET_DESCRIPTION_CHARS,
        )


@dataclass(frozen=True, slots=True)
class ResolvedVisualStyle:
    """Requested selector plus the concrete immutable preset it resolved to."""

    requested_id: str
    preset: VisualStylePreset

    def __post_init__(self) -> None:
        _preset_id(self.requested_id, field="requested_id")

    @property
    def resolved_id(self) -> str:
        return self.preset.id


__all__ = [
    "MAX_PRESET_DESCRIPTION_CHARS",
    "MAX_PRESET_ID_CHARS",
    "MAX_PRESET_LABEL_CHARS",
    "MAX_PREVIEW_ASSET_CHARS",
    "ResolvedVisualStyle",
    "VisualStylePreset",
]
