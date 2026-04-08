"""
Service for fetching and caching the vision-capable model list.

Reuses the same OpenRouter public API and local fallback as the LLM model
list service, but filters for models that accept image input.
"""

import json
import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
FALLBACK_FILE = (
    Path(__file__).parent.parent / "config" / "vision_model_list_fallback.json"
)
CACHE_TTL_SECONDS = 86400  # 24 hours

_cache: list[dict] | None = None
_cache_timestamp: float = 0

OPENROUTER_SLUG_TO_VISION_PROVIDER: dict[str, str] = {
    "openai": "OPENAI",
    "anthropic": "ANTHROPIC",
    "google": "GOOGLE",
    "mistralai": "MISTRAL",
    "x-ai": "XAI",
}


def _format_context_length(length: int | None) -> str | None:
    if not length:
        return None
    if length >= 1_000_000:
        return f"{length / 1_000_000:g}M"
    if length >= 1_000:
        return f"{length / 1_000:g}K"
    return str(length)


async def _fetch_from_openrouter() -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(OPENROUTER_API_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        logger.warning("Failed to fetch from OpenRouter API for vision models: %s", e)
        return None


def _load_fallback() -> list[dict]:
    try:
        with open(FALLBACK_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load vision model fallback list: %s", e)
        return []


def _is_vision_model(model: dict) -> bool:
    """Return True if the model accepts image input and outputs text."""
    arch = model.get("architecture", {})
    input_mods = arch.get("input_modalities", [])
    output_mods = arch.get("output_modalities", [])
    return "image" in input_mods and "text" in output_mods


def _process_vision_models(raw_models: list[dict]) -> list[dict]:
    processed: list[dict] = []

    for model in raw_models:
        model_id: str = model.get("id", "")
        name: str = model.get("name", "")
        context_length = model.get("context_length")

        if "/" not in model_id:
            continue

        if not _is_vision_model(model):
            continue

        provider_slug, model_name = model_id.split("/", 1)
        context_window = _format_context_length(context_length)

        processed.append(
            {
                "value": model_id,
                "label": name,
                "provider": "OPENROUTER",
                "context_window": context_window,
            }
        )

        native_provider = OPENROUTER_SLUG_TO_VISION_PROVIDER.get(provider_slug)
        if native_provider:
            if native_provider == "GOOGLE" and not model_name.startswith("gemini-"):
                continue

            processed.append(
                {
                    "value": model_name,
                    "label": name,
                    "provider": native_provider,
                    "context_window": context_window,
                }
            )

    return processed


async def get_vision_model_list() -> list[dict]:
    global _cache, _cache_timestamp

    if _cache is not None and (time.time() - _cache_timestamp) < CACHE_TTL_SECONDS:
        return _cache

    raw_models = await _fetch_from_openrouter()

    if raw_models is None:
        logger.info("Using fallback vision model list")
        return _load_fallback()

    processed = _process_vision_models(raw_models)

    _cache = processed
    _cache_timestamp = time.time()

    return processed
