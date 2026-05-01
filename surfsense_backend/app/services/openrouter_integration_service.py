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
import hashlib
import logging
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"

# Sentinel value stored on each generated config so we can distinguish
# dynamic OpenRouter entries from hand-written YAML entries during refresh.
_OPENROUTER_DYNAMIC_MARKER = "__openrouter_dynamic__"

# Fixed negative ID for the virtual ``openrouter/free`` auto-select entry.
# Chosen to sit far below any reasonable ``id_offset`` so it never collides
# with per-model stable IDs.
_FREE_ROUTER_ID = -9_999_999

# Width of the hash space used by ``_stable_config_id``. 9_000_000 provides
# enough headroom to avoid frequent collisions for OpenRouter's catalogue
# (~300 models) while keeping IDs comfortably within Postgres INTEGER range.
_STABLE_ID_HASH_WIDTH = 9_000_000


def _stable_config_id(model_id: str, offset: int, taken: set[int]) -> int:
    """Derive a deterministic negative config ID from ``model_id``.

    The same ``model_id`` always hashes to the same base value so thread pins
    survive catalogue churn (models appearing/disappearing/reordering between
    refreshes). On collision we decrement until we find an unused slot; this
    keeps the mapping stable for the first config that claimed a slot and
    only shifts collisions, which is much less disruptive than the legacy
    index-based scheme that reshuffled every ID when the catalogue changed.
    """
    digest = hashlib.blake2b(model_id.encode("utf-8"), digest_size=6).digest()
    base = offset - (int.from_bytes(digest, "big") % _STABLE_ID_HASH_WIDTH)
    cid = base
    while cid in taken:
        cid -= 1
    taken.add(cid)
    return cid


def _openrouter_tier(model: dict) -> str:
    """Classify an OpenRouter model as ``"free"`` or ``"premium"``.

    Per OpenRouter's API contract, a model is free if:
    - Its id ends with ``:free`` (OpenRouter's own free-variant convention), or
    - Both ``pricing.prompt`` and ``pricing.completion`` are zero strings.

    Anything else (missing pricing, non-zero pricing) falls through to
    ``"premium"`` so we never under-charge users. This derivation runs off the
    already-cached /api/v1/models payload, so it adds no network cost.
    """
    if model.get("id", "").endswith(":free"):
        return "free"
    pricing = model.get("pricing") or {}
    prompt = str(pricing.get("prompt", "")).strip()
    completion = str(pricing.get("completion", "")).strip()
    if prompt == "0" and completion == "0":
        return "free"
    return "premium"


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


def _build_free_router_config(settings: dict[str, Any]) -> dict[str, Any]:
    """Build the virtual ``openrouter/free`` auto-select config entry.

    This exposes OpenRouter's Free Models Router as a single selectable
    option. LiteLLM forwards ``openrouter/openrouter/free`` and OpenRouter
    picks a capable free model per request (availability varies, account-wide
    rate limit is ~20 req/min).
    """
    return {
        "id": _FREE_ROUTER_ID,
        "name": "OpenRouter Free (Auto-Select)",
        "description": (
            "OpenRouter picks a capable free model per request. "
            "~20 req/min account-wide; availability varies."
        ),
        "provider": "OPENROUTER",
        "model_name": "openrouter/free",
        "api_key": settings.get("api_key", ""),
        "api_base": "",
        "billing_tier": "free",
        "rpm": settings.get("free_rpm", 20),
        "tpm": settings.get("free_tpm", 100_000),
        "anonymous_enabled": settings.get("anonymous_enabled_free", False),
        "seo_enabled": False,
        "seo_slug": None,
        "quota_reserve_tokens": settings.get("quota_reserve_tokens", 4000),
        "litellm_params": dict(settings.get("litellm_params") or {}),
        "system_instructions": settings.get("system_instructions", ""),
        "use_default_system_instructions": settings.get(
            "use_default_system_instructions", True
        ),
        "citations_enabled": settings.get("citations_enabled", True),
        "router_pool_eligible": False,
        _OPENROUTER_DYNAMIC_MARKER: True,
    }


def _generate_configs(
    raw_models: list[dict],
    settings: dict[str, Any],
) -> list[dict]:
    """Convert raw OpenRouter model entries into global LLM config dicts.

    Tier (``billing_tier``) is derived per-model from OpenRouter's own API
    signals via ``_openrouter_tier`` — there is no longer a uniform YAML
    override. Config IDs are derived via ``_stable_config_id`` so they
    survive catalogue churn across refreshes.

    Router-pool membership is tier-aware:

    - Premium OR models join the LiteLLM router pool (``router_pool_eligible=True``)
      so sub-agent ``model="auto"`` flows benefit from load balancing and
      failover across the curated YAML configs and the OR premium passthrough.
    - Free OR models and the virtual ``openrouter/free`` entry stay excluded
      (``router_pool_eligible=False``). LiteLLM Router tracks rate limits per
      deployment, but OpenRouter enforces a single global free-tier quota
      (~20 RPM + 50-1000 daily requests account-wide across every ``:free``
      model), so rotating across many free deployments would only burn the
      shared bucket faster. Free OR models remain fully available for user-
      facing Auto-mode thread pinning via ``auto_model_pin_service``.
    """
    id_offset: int = settings.get("id_offset", -10000)
    api_key: str = settings.get("api_key", "")
    seo_enabled: bool = settings.get("seo_enabled", False)
    quota_reserve_tokens: int = settings.get("quota_reserve_tokens", 4000)
    rpm: int = settings.get("rpm", 200)
    tpm: int = settings.get("tpm", 1_000_000)
    free_rpm: int = settings.get("free_rpm", 20)
    free_tpm: int = settings.get("free_tpm", 100_000)
    anon_paid: bool = settings.get("anonymous_enabled_paid", False)
    anon_free: bool = settings.get("anonymous_enabled_free", False)
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

    configs: list[dict] = []

    if settings.get("free_router_enabled", True) and api_key:
        configs.append(_build_free_router_config(settings))

    taken: set[int] = set()
    if configs:
        taken.add(_FREE_ROUTER_ID)

    for model in text_models:
        model_id: str = model["id"]
        name: str = model.get("name", model_id)
        tier = _openrouter_tier(model)

        cfg: dict[str, Any] = {
            "id": _stable_config_id(model_id, id_offset, taken),
            "name": name,
            "description": f"{name} via OpenRouter",
            "billing_tier": tier,
            "anonymous_enabled": anon_free if tier == "free" else anon_paid,
            "seo_enabled": seo_enabled,
            "seo_slug": None,
            "quota_reserve_tokens": quota_reserve_tokens,
            "provider": "OPENROUTER",
            "model_name": model_id,
            "api_key": api_key,
            "api_base": "",
            "rpm": free_rpm if tier == "free" else rpm,
            "tpm": free_tpm if tier == "free" else tpm,
            "litellm_params": dict(litellm_params),
            "system_instructions": system_instructions,
            "use_default_system_instructions": use_default,
            "citations_enabled": citations_enabled,
            # Premium OR deployments join the LiteLLM router pool so sub-agent
            # model="auto" flows can load-balance / fail over across them.
            # Free OR deployments stay out: OpenRouter's free tier is a single
            # account-wide quota, so per-deployment routing can't spread load
            # there — it just drains the shared bucket faster.
            "router_pool_eligible": tier == "premium",
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

        tier_counts = self._tier_counts(self._configs)
        logger.info(
            "OpenRouter integration: loaded %d models (free=%d, premium=%d)",
            len(self._configs),
            tier_counts["free"],
            tier_counts["premium"],
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

        tier_counts = self._tier_counts(new_configs)
        logger.info(
            "OpenRouter refresh: updated to %d models (free=%d, premium=%d)",
            len(new_configs),
            tier_counts["free"],
            tier_counts["premium"],
        )

        # Rebuild the LiteLLM router so freshly fetched configs flow through
        # (the router filters dynamic OR entries out of its pool, but a
        # refresh still needs to pick up any static-config edits and reset
        # cached context-window profiles).
        try:
            from app.config import config as _app_config
            from app.services.llm_router_service import LLMRouterService
            from app.services.llm_router_service import (
                _router_instance_cache as _chat_router_cache,
            )

            LLMRouterService.rebuild(
                _app_config.GLOBAL_LLM_CONFIGS,
                getattr(_app_config, "ROUTER_SETTINGS", None),
            )
            _chat_router_cache.clear()
        except Exception as exc:
            logger.warning(
                "OpenRouter refresh: router rebuild skipped (%s)", exc
            )

    @staticmethod
    def _tier_counts(configs: list[dict]) -> dict[str, int]:
        counts = {"free": 0, "premium": 0}
        for cfg in configs:
            tier = str(cfg.get("billing_tier", "")).lower()
            if tier in counts:
                counts[tier] += 1
        return counts

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
