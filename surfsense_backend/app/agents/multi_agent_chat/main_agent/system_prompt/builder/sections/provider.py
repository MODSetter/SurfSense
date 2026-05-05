"""Provider-specific style hints."""

from __future__ import annotations

from ..provider_hints import build_provider_hint_block, detect_provider_variant


def build_provider_section(*, model_name: str | None) -> str:
    return build_provider_hint_block(detect_provider_variant(model_name))
