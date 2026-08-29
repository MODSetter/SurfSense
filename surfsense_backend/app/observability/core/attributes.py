"""Coerce attribute mappings to OTel-safe scalars."""

from __future__ import annotations

from typing import Any


def clean_attributes(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Drop None/empty values; stringify non-scalars."""
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float):
            cleaned[key] = value
            continue
        text = str(value)
        if text:
            cleaned[key] = text
    return cleaned
