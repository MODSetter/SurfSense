"""Shared Requesty model normalization.

Requesty (https://router.requesty.ai) is an OpenAI-compatible LLM router.
Its ``/v1/models`` catalogue carries richer, Requesty-specific capability
metadata than a generic OpenAI-compatible ``/models`` response, so keep all
Requesty filtering and capability extraction here -- mirroring
``openrouter_model_normalizer`` -- so GLOBAL catalogue generation and BYOK
discovery agree.

Unlike OpenRouter, Requesty exposes capabilities as flat booleans
(``supports_tool_calling`` / ``supports_reasoning`` / ``supports_vision`` /
``supports_image_generation``) rather than an ``architecture`` block plus a
``supported_parameters`` array, and it reports context size as
``context_window`` rather than ``context_length``. This module maps those
fields onto the same normalized shape the rest of the backend consumes.
"""

from __future__ import annotations

from typing import Any

from app.db import ModelSource

MIN_CONTEXT_LENGTH = 100_000

EXCLUDED_PROVIDER_SLUGS: set[str] = {"amazon"}
EXCLUDED_MODEL_IDS: set[str] = set()
EXCLUDED_MODEL_SUFFIXES: tuple[str, ...] = ("-deep-research",)


def is_image_output_model(model: dict[str, Any]) -> bool:
    return bool(model.get("supports_image_generation"))


def is_text_output_model(model: dict[str, Any]) -> bool:
    # Requesty entries are chat-completion models (``api == "chat"``). Treat a
    # model as text output whenever it is not an image-generation model.
    return not is_image_output_model(model)


def supports_image_input(model: dict[str, Any]) -> bool:
    return bool(model.get("supports_vision"))


def supports_tool_calling(model: dict[str, Any]) -> bool:
    return bool(model.get("supports_tool_calling"))


def has_sufficient_context(model: dict[str, Any]) -> bool:
    return int(model.get("context_window") or 0) >= MIN_CONTEXT_LENGTH


def is_compatible_provider(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id") or "")
    slug = model_id.split("/", 1)[0] if "/" in model_id else ""
    return slug not in EXCLUDED_PROVIDER_SLUGS


def is_allowed_model(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id") or "")
    if model_id in EXCLUDED_MODEL_IDS:
        return False
    base_id = model_id.split(":")[0]
    return not base_id.endswith(EXCLUDED_MODEL_SUFFIXES)


def is_requesty_chat_model(model: dict[str, Any]) -> bool:
    return (
        "/" in str(model.get("id") or "")
        and is_text_output_model(model)
        and supports_tool_calling(model)
        and has_sufficient_context(model)
        and is_compatible_provider(model)
        and is_allowed_model(model)
    )


def is_requesty_image_model(model: dict[str, Any]) -> bool:
    return (
        "/" in str(model.get("id") or "")
        and is_image_output_model(model)
        and is_compatible_provider(model)
        and is_allowed_model(model)
    )


def normalize_requesty_models(
    raw_models: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for model in raw_models:
        if not is_requesty_chat_model(model):
            continue
        model_id = str(model.get("id") or "")
        normalized.append(
            {
                "model_id": model_id,
                "display_name": model.get("name") or model_id,
                "source": ModelSource.DISCOVERED,
                "supports_chat": True,
                "max_input_tokens": model.get("context_window"),
                "supports_image_input": supports_image_input(model),
                "supports_tools": supports_tool_calling(model),
                "supports_image_generation": False,
                "metadata": model,
            }
        )
    return normalized


__all__ = [
    "MIN_CONTEXT_LENGTH",
    "has_sufficient_context",
    "is_allowed_model",
    "is_compatible_provider",
    "is_image_output_model",
    "is_requesty_chat_model",
    "is_requesty_image_model",
    "is_text_output_model",
    "normalize_requesty_models",
    "supports_image_input",
    "supports_tool_calling",
]
