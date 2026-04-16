"""
OpenRouter Integration Service

Dynamically fetches all available models from the OpenRouter public API
and generates virtual global LLM config entries. These entries are injected
into config.GLOBAL_LLM_CONFIGS so they appear alongside static YAML configs
in the model selector.

All actual LLM calls go through LiteLLM with the ``openrouter/`` prefix --
this service only manages the catalogue, not the inference path.
"""

import asyncio
import logging
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"

# Sentinel value stored on each generated config so we can distinguish
# dynamic OpenRouter entries from hand-written YAML entries during refresh.
_OPENROUTER_DYNAMIC_MARKER = "__openrouter_dynamic__"


def _is_text_output_model(model: dict) -> bool:
    """Return True if the model produces text output only (skip image/audio generators)."""
    output_mods = model.get("architecture", {}).get("output_modalities", [])
    return output_mods == ["text"]


def _supports_tool_calling(model: dict) -> bool:
    """Return True if the model supports function/tool calling."""
    supported = model.get("supported_parameters") or []
    return "tools" in supported


MIN_CONTEXT_LENGTH = 100_000

# Provider slugs whose backend is fundamentally incompatible with our agent's
# tool-call message flow (e.g. Amazon Bedrock requires toolConfig alongside
# tool history which OpenRouter doesn't relay).
_EXCLUDED_PROVIDER_SLUGS = {"amazon"}

_EXCLUDED_MODEL_IDS: set[str] = {
    # Deprecated / removed upstream
    "openai/gpt-4-1106-preview",
    "openai/gpt-4-turbo-preview",
    # Permanently no-capacity variant
    "openai/gpt-4o:extended",
    # Non-serverless model that requires a dedicated endpoint
    "arcee-ai/virtuoso-large",
    # Deep-research models reject standard params (temperature, etc.)
    "openai/o3-deep-research",
    "openai/o4-mini-deep-research",
}

_EXCLUDED_MODEL_SUFFIXES: tuple[str, ...] = ("-deep-research",)


def _has_sufficient_context(model: dict) -> bool:
    """Return True if the model's context window is at least MIN_CONTEXT_LENGTH."""
    ctx = model.get("context_length") or 0
    return ctx >= MIN_CONTEXT_LENGTH


def _is_compatible_provider(model: dict) -> bool:
    """Return False for models from providers known to be incompatible."""
    model_id = model.get("id", "")
    slug = model_id.split("/", 1)[0] if "/" in model_id else ""
    return slug not in _EXCLUDED_PROVIDER_SLUGS


def _is_allowed_model(model: dict) -> bool:
    """Return False for specific model IDs known to be broken or incompatible."""
    model_id = model.get("id", "")
    if model_id in _EXCLUDED_MODEL_IDS:
        return False
    base_id = model_id.split(":")[0]
    return not base_id.endswith(_EXCLUDED_MODEL_SUFFIXES)


def _fetch_models_sync() -> list[dict] | None:
    """Synchronous fetch for use during startup (before the event loop is running)."""
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(OPENROUTER_API_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        logger.warning("Failed to fetch OpenRouter models (sync): %s", e)
        return None


async def _fetch_models_async() -> list[dict] | None:
    """Async fetch for background refresh."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(OPENROUTER_API_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
    except Exception as e:
        logger.warning("Failed to fetch OpenRouter models (async): %s", e)
        return None


def _generate_configs(
    raw_models: list[dict],
    settings: dict[str, Any],
) -> list[dict]:
    """
    Convert raw OpenRouter model entries into global LLM config dicts.

    Models are sorted by ID for deterministic, stable ID assignment across
    restarts and refreshes.
    """
    id_offset: int = settings.get("id_offset", -10000)
    api_key: str = settings.get("api_key", "")
    billing_tier: str = settings.get("billing_tier", "premium")
    anonymous_enabled: bool = settings.get("anonymous_enabled", False)
    seo_enabled: bool = settings.get("seo_enabled", False)
    quota_reserve_tokens: int = settings.get("quota_reserve_tokens", 4000)
    rpm: int = settings.get("rpm", 200)
    tpm: int = settings.get("tpm", 1000000)
    litellm_params: dict = settings.get("litellm_params") or {}
    system_instructions: str = settings.get("system_instructions", "")
    use_default: bool = settings.get("use_default_system_instructions", True)
    citations_enabled: bool = settings.get("citations_enabled", True)

    text_models = [
        m
        for m in raw_models
        if _is_text_output_model(m)
        and _supports_tool_calling(m)
        and _has_sufficient_context(m)
        and _is_compatible_provider(m)
        and _is_allowed_model(m)
        and "/" in m.get("id", "")
    ]
    text_models.sort(key=lambda m: m["id"])

    configs: list[dict] = []
    for idx, model in enumerate(text_models):
        model_id: str = model["id"]
        name: str = model.get("name", model_id)

        cfg: dict[str, Any] = {
            "id": id_offset - idx,
            "name": name,
            "description": f"{name} via OpenRouter",
            "billing_tier": billing_tier,
            "anonymous_enabled": anonymous_enabled,
            "seo_enabled": seo_enabled,
            "seo_slug": None,
            "quota_reserve_tokens": quota_reserve_tokens,
            "provider": "OPENROUTER",
            "model_name": model_id,
            "api_key": api_key,
            "api_base": "",
            "rpm": rpm,
            "tpm": tpm,
            "litellm_params": dict(litellm_params),
            "system_instructions": system_instructions,
            "use_default_system_instructions": use_default,
            "citations_enabled": citations_enabled,
            _OPENROUTER_DYNAMIC_MARKER: True,
        }
        configs.append(cfg)

    return configs


class OpenRouterIntegrationService:
    """Singleton that manages the dynamic OpenRouter model catalogue."""

    _instance: "OpenRouterIntegrationService | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {}
        self._configs: list[dict] = []
        self._configs_by_id: dict[int, dict] = {}
        self._initialized = False
        self._refresh_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> "OpenRouterIntegrationService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._instance is not None and cls._instance._initialized

    # ------------------------------------------------------------------
    # Initialisation (called at startup, before event loop for Celery)
    # ------------------------------------------------------------------

    def initialize(self, settings: dict[str, Any]) -> list[dict]:
        """
        Fetch models synchronously and generate configs.
        Returns the generated configs list.
        """
        self._settings = settings
        raw_models = _fetch_models_sync()
        if raw_models is None:
            logger.warning("OpenRouter integration: could not fetch models at startup")
            self._initialized = True
            return []

        self._configs = _generate_configs(raw_models, settings)
        self._configs_by_id = {c["id"]: c for c in self._configs}
        self._initialized = True

        logger.info(
            "OpenRouter integration: loaded %d models (IDs %d to %d)",
            len(self._configs),
            self._configs[0]["id"] if self._configs else 0,
            self._configs[-1]["id"] if self._configs else 0,
        )
        return self._configs

    # ------------------------------------------------------------------
    # Background refresh
    # ------------------------------------------------------------------

    async def refresh(self) -> None:
        """Re-fetch from OpenRouter and atomically swap configs in GLOBAL_LLM_CONFIGS."""
        raw_models = await _fetch_models_async()
        if raw_models is None:
            logger.warning("OpenRouter refresh: fetch failed, keeping stale list")
            return

        new_configs = _generate_configs(raw_models, self._settings)
        new_by_id = {c["id"]: c for c in new_configs}

        from app.config import config as app_config

        static_configs = [
            c
            for c in app_config.GLOBAL_LLM_CONFIGS
            if not c.get(_OPENROUTER_DYNAMIC_MARKER)
        ]
        app_config.GLOBAL_LLM_CONFIGS = static_configs + new_configs

        self._configs = new_configs
        self._configs_by_id = new_by_id

        logger.info("OpenRouter refresh: updated to %d models", len(new_configs))

    async def _refresh_loop(self, interval_hours: float) -> None:
        interval_sec = interval_hours * 3600
        while True:
            await asyncio.sleep(interval_sec)
            try:
                await self.refresh()
            except Exception:
                logger.exception("OpenRouter background refresh failed")

    def start_background_refresh(self, interval_hours: float) -> None:
        if interval_hours <= 0:
            return
        loop = asyncio.get_event_loop()
        self._refresh_task = loop.create_task(self._refresh_loop(interval_hours))
        logger.info(
            "OpenRouter background refresh started (every %.1fh)", interval_hours
        )

    def stop_background_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            self._refresh_task = None
            logger.info("OpenRouter background refresh stopped")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_configs(self) -> list[dict]:
        return self._configs

    def get_config_by_id(self, config_id: int) -> dict | None:
        return self._configs_by_id.get(config_id)
