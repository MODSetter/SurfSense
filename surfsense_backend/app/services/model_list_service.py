"""
Service for fetching and caching the available LLM model list.

Uses the OpenRouter public API as the primary source, with a local
fallback JSON file when the API is unreachable.
"""

import json
import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
FALLBACK_FILE = Path(__file__).parent.parent / "config" / "model_list_fallback.json"
CACHE_TTL_SECONDS = 86400  # 24 hours

# In-memory cache
_cache: list[dict] | None = None
_cache_timestamp: float = 0

# Maps OpenRouter provider slug → our LiteLLMProvider enum value.
# Only providers where the model-name part (after the slash) can be
# used directly with the native provider's litellm prefix are listed.
#
# Excluded slugs and why:
#   "deepseek"  - Native API only accepts "deepseek-chat" / "deepseek-reasoner";
#                 OpenRouter uses different names (deepseek-v3.2, deepseek-r1, ...).
#   "qwen"      - Most OpenRouter Qwen entries are open-source models (qwen3-32b, ...)
#                 that are NOT available on the Dashscope API.
#   "ai21"      - OpenRouter name "jamba-large-1.7" != AI21 API name "jamba-1.5-large".
#   "microsoft" - OpenRouter "microsoft/" = open-source Phi/WizardLM, NOT Azure
#                 OpenAI deployments (which require deployment names, not model ids).
OPENROUTER_SLUG_TO_PROVIDER: dict[str, str] = {
    "openai": "OPENAI",
    "anthropic": "ANTHROPIC",
    "google": "GOOGLE",
    "mistralai": "MISTRAL",
    "cohere": "COHERE",
    "x-ai": "XAI",
    "perplexity": "PERPLEXITY",
}


def _format_context_length(length: int | None) -> str | None:
    """Convert a raw token count to a human-readable string (e.g. 128K, 1M)."""
    if not length:
        return None
    if length >= 1_000_000:
        return f"{length / 1_000_000:g}M"
    if length >= 1_000:
        return f"{length / 1_000:g}K"
    return str(length)


async def _fetch_from_openrouter() -> list[dict] | None:
    """Try fetching the model catalogue from the OpenRouter public API."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(OPENROUTER_API_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        logger.warning("Failed to fetch from OpenRouter API: %s", e)
        return None


def _load_fallback() -> list[dict]:
    """Load the local fallback model list."""
    try:
        with open(FALLBACK_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("data", [])
    except Exception as e:
        logger.error("Failed to load fallback model list: %s", e)
        return []


def _is_text_output_model(model: dict) -> bool:
    """Return True if the model's output is text-only (no audio/image generation)."""
    output_mods = model.get("architecture", {}).get("output_modalities", [])
    return output_mods == ["text"]


def _process_models(raw_models: list[dict]) -> list[dict]:
    """
    Transform raw OpenRouter model entries into a flat list of
    {value, label, provider, context_window} dicts.

    Only text-output models are included (audio/image generators are skipped).

    Each OpenRouter model is emitted once for OPENROUTER (full id) and,
    when the slug maps to a native provider, once more with just the
    model-name portion.
    """
    processed: list[dict] = []

    for model in raw_models:
        model_id: str = model.get("id", "")
        name: str = model.get("name", "")
        context_length = model.get("context_length")

        if "/" not in model_id:
            continue

        if not _is_text_output_model(model):
            continue

        provider_slug, model_name = model_id.split("/", 1)
        context_window = _format_context_length(context_length)

        # 1) Always emit for OPENROUTER (value = full OpenRouter id)
        processed.append(
            {
                "value": model_id,
                "label": name,
                "provider": "OPENROUTER",
                "context_window": context_window,
            }
        )

        # 2) Emit for the native provider when we have a mapping
        native_provider = OPENROUTER_SLUG_TO_PROVIDER.get(provider_slug)
        if native_provider:
            # Google's Gemini API only serves gemini-* models.
            # Open-source models like gemma-* are NOT available through it.
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


async def get_model_list() -> list[dict]:
    """
    Return the processed model list, using in-memory cache when fresh.
    Tries the OpenRouter API first, falls back to the local JSON file.
    """
    global _cache, _cache_timestamp

    if _cache is not None and (time.time() - _cache_timestamp) < CACHE_TTL_SECONDS:
        return _cache

    raw_models = await _fetch_from_openrouter()

    if raw_models is None:
        logger.info("Using fallback model list")
        raw_models = _load_fallback()

    processed = _process_models(raw_models)

    _cache = processed
    _cache_timestamp = time.time()

    return processed
