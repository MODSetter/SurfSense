"""Shared OpenRouter model normalization.

OpenRouter metadata is richer than generic OpenAI-compatible ``/models``
responses. Keep all OpenRouter filtering and capability extraction here so
GLOBAL catalogue generation and BYOK discovery agree.
"""

from __future__ import annotations

from typing import Any

from app.db import ModelSource

MIN_CONTEXT_LENGTH = 100_000

EXCLUDED_PROVIDER_SLUGS = {"amazon"}
EXCLUDED_MODEL_IDS: set[str] = {
    "openai/gpt-4-1106-preview",
    "openai/gpt-4-turbo-preview",
    "openai/gpt-4o:extended",
    "arcee-ai/virtuoso-large",
    "openai/o3-deep-research",
    "openai/o4-mini-deep-research",
    "openrouter/free",
}
EXCLUDED_MODEL_SUFFIXES: tuple[str, ...] = ("-deep-research",)

# Variant suffixes after the ``:`` in an OpenRouter id. ``:batch`` models carry
# full chat metadata in ``/models`` but reject chat completions with
# ``404 "This model is only available through the Batch API"``, so they are
# unusable for streaming chat no matter how well they score.
EXCLUDED_MODEL_VARIANTS: frozenset[str] = frozenset({"batch"})


def is_text_output_model(model: dict[str, Any]) -> bool:
    output_mods = model.get("architecture", {}).get("output_modalities", [])
    return output_mods == ["text"]


def is_image_output_model(model: dict[str, Any]) -> bool:
    output_mods = model.get("architecture", {}).get("output_modalities", []) or []
    return "image" in output_mods


def supports_image_input(model: dict[str, Any]) -> bool:
    input_mods = model.get("architecture", {}).get("input_modalities", []) or []
    return "image" in input_mods


def supports_tool_calling(model: dict[str, Any]) -> bool:
    supported = model.get("supported_parameters") or []
    return "tools" in supported


def has_sufficient_context(model: dict[str, Any]) -> bool:
    return int(model.get("context_length") or 0) >= MIN_CONTEXT_LENGTH


def is_compatible_provider(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id") or "")
    slug = model_id.split("/", 1)[0] if "/" in model_id else ""
    return slug not in EXCLUDED_PROVIDER_SLUGS


def is_allowed_model(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id") or "")
    if model_id in EXCLUDED_MODEL_IDS:
        return False
    base_id, _, variant = model_id.partition(":")
    if variant in EXCLUDED_MODEL_VARIANTS:
        return False
    return not base_id.endswith(EXCLUDED_MODEL_SUFFIXES)


def is_openrouter_chat_model(model: dict[str, Any]) -> bool:
    return (
        "/" in str(model.get("id") or "")
        and is_text_output_model(model)
        and supports_tool_calling(model)
        and has_sufficient_context(model)
        and is_compatible_provider(model)
        and is_allowed_model(model)
    )


def is_openrouter_image_model(model: dict[str, Any]) -> bool:
    return (
        "/" in str(model.get("id") or "")
        and is_image_output_model(model)
        and is_compatible_provider(model)
        and is_allowed_model(model)
    )


def normalize_openrouter_models(
    raw_models: list[dict[str, Any]],
    blocked_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter and flatten OpenRouter's ``/models`` payload.

    ``blocked_ids`` comes from the compatibility sweep, which probes models that
    pass every metadata check above and still cannot serve a turn. Passed in
    rather than read here so this module stays sync and unit-testable.
    """
    normalized: list[dict[str, Any]] = []
    for model in raw_models:
        if not is_openrouter_chat_model(model):
            continue
        model_id = str(model.get("id") or "")
        if blocked_ids and model_id in blocked_ids:
            continue
        normalized.append(
            {
                "model_id": model_id,
                "display_name": model.get("name") or model_id,
                "source": ModelSource.DISCOVERED,
                "supports_chat": True,
                "max_input_tokens": model.get("context_length"),
                "supports_image_input": supports_image_input(model),
                "supports_tools": supports_tool_calling(model),
                "supports_image_generation": False,
                "metadata": model,
            }
        )
    return normalized


__all__ = [
    "EXCLUDED_MODEL_VARIANTS",
    "MIN_CONTEXT_LENGTH",
    "has_sufficient_context",
    "is_allowed_model",
    "is_compatible_provider",
    "is_image_output_model",
    "is_openrouter_chat_model",
    "is_openrouter_image_model",
    "is_text_output_model",
    "normalize_openrouter_models",
    "supports_image_input",
    "supports_tool_calling",
]
