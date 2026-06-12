import copy
import os
import shutil
from functools import lru_cache
from pathlib import Path

import yaml
from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from dotenv import load_dotenv
from rerankers import Reranker

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env_file = BASE_DIR / ".env"
load_dotenv(env_file)

os.environ.setdefault("OR_APP_NAME", "SurfSense")
os.environ.setdefault("OR_SITE_URL", "https://surfsense.com")


@lru_cache(maxsize=8)
def _read_global_config_yaml(path_str: str) -> dict:
    """Read and parse ``global_llm_config.yaml`` once per resolved path.

    Cached so the seven ``load_*`` helpers (and their re-invocations during
    startup) don't re-open and re-parse the same file repeatedly. Keyed on the
    resolved path string so tests that monkeypatch ``BASE_DIR`` to a unique
    ``tmp_path`` still get a fresh parse. Callers MUST treat the returned dict
    as read-only and deep-copy any section they intend to mutate.
    """
    f = Path(path_str)
    if not f.exists():
        return {}
    try:
        with open(f, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        print(f"Warning: Failed to read global_llm_config.yaml: {e}")
        return {}


def _global_config_data() -> dict:
    """Return the parsed global config YAML for the current ``BASE_DIR``.

    ``BASE_DIR`` is read at call time (not bound at import) so a
    ``monkeypatch.setattr(config, "BASE_DIR", tmp_path)`` is honored.
    """
    path = BASE_DIR / "app" / "config" / "global_llm_config.yaml"
    return _read_global_config_yaml(str(path))


def is_ffmpeg_installed():
    """
    Check if ffmpeg is installed on the current system.

    Returns:
        bool: True if ffmpeg is installed, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


def load_global_llm_configs():
    """
    Load global LLM configurations from YAML file.
    Falls back to example file if main file doesn't exist.

    Returns:
        list: List of global LLM config dictionaries, or empty list if file doesn't exist
    """
    data = _global_config_data()
    if not data:
        # No global configs available
        return []

    try:
        # Deep-copy so the in-place mutations below (setdefault, scoring
        # stamps) never leak into the cached YAML structure.
        configs = copy.deepcopy(data.get("global_llm_configs", []))

        # Lazy import keeps the `app.config` -> `app.services` edge one-way
        # and matches the `provider_api_base` pattern used elsewhere.
        from app.services.provider_capabilities import derive_supports_image_input

        seen_slugs: dict[str, int] = {}
        for cfg in configs:
            cfg.setdefault("billing_tier", "free")
            cfg.setdefault("anonymous_enabled", False)
            cfg.setdefault("seo_enabled", False)
            # Capability flag: explicit YAML override always wins. When the
            # operator has not annotated the model, defer to LiteLLM's
            # authoritative model map (`supports_vision`) which already
            # knows GPT-5.x / GPT-4o / Claude 3.x / Gemini 2.x are
            # vision-capable. Unknown / unmapped models default-allow so
            # we don't lock the user out of a freshly added third-party
            # entry; the streaming-task safety net (driven by
            # `is_known_text_only_chat_model`) is the only place a False
            # actually blocks a request.
            if "supports_image_input" not in cfg:
                litellm_params = cfg.get("litellm_params") or {}
                base_model = (
                    litellm_params.get("base_model")
                    if isinstance(litellm_params, dict)
                    else None
                )
                cfg["supports_image_input"] = derive_supports_image_input(
                    provider=cfg.get("provider"),
                    model_name=cfg.get("model_name"),
                    base_model=base_model,
                    custom_provider=cfg.get("custom_provider"),
                )

            if cfg.get("seo_enabled") and cfg.get("seo_slug"):
                slug = cfg["seo_slug"]
                if slug in seen_slugs:
                    print(
                        f"Warning: Duplicate seo_slug '{slug}' in global LLM configs "
                        f"(ids {seen_slugs[slug]} and {cfg.get('id')})"
                    )
                else:
                    seen_slugs[slug] = cfg.get("id", 0)

        # Stamp Auto (Fastest) ranking metadata. YAML configs are always
        # Tier A — operator-curated, locked first when premium-eligible.
        # The OpenRouter refresh tick later re-stamps health for any cfg
        # whose provider == "OPENROUTER" via _enrich_health.
        try:
            from app.services.quality_score import static_score_yaml

            for cfg in configs:
                cfg["auto_pin_tier"] = "A"
                static_q = static_score_yaml(cfg)
                cfg["quality_score_static"] = static_q
                cfg["quality_score"] = static_q
                cfg["quality_score_health"] = None
                # YAML cfgs whose provider is OPENROUTER are also subject
                # to health gating against their own /endpoints data — a
                # hand-picked dead OR model is still dead. _enrich_health
                # re-stamps health_gated for them on the next refresh tick.
                cfg["health_gated"] = False
        except Exception as e:
            print(f"Warning: Failed to score global LLM configs: {e}")

        # Planner LLM is a singleton role. If an operator accidentally
        # marks multiple configs ``is_planner: true``, only the first one
        # is used at runtime — surface the others at startup so the
        # mistake is caught before traffic, not silently buried.
        planner_cfgs = [c for c in configs if c.get("is_planner") is True]
        if len(planner_cfgs) > 1:
            extra_ids = [c.get("id") for c in planner_cfgs[1:]]
            print(
                "Warning: Multiple global LLM configs marked is_planner=true "
                f"(ids {[c.get('id') for c in planner_cfgs]}); using id "
                f"{planner_cfgs[0].get('id')} and ignoring {extra_ids}"
            )

        return configs
    except Exception as e:
        print(f"Warning: Failed to load global LLM configs: {e}")
        return []


def load_router_settings():
    """
    Load router settings for Auto mode from YAML file.
    Falls back to default settings if not found.

    Returns:
        dict: Router settings dictionary
    """
    # Default router settings
    default_settings = {
        "routing_strategy": "usage-based-routing",
        "num_retries": 3,
        "allowed_fails": 3,
        "cooldown_time": 60,
    }

    data = _global_config_data()
    if not data:
        return default_settings

    try:
        settings = data.get("router_settings", {})
        # Merge with defaults
        return {**default_settings, **settings}
    except Exception as e:
        print(f"Warning: Failed to load router settings: {e}")
        return default_settings


def load_global_image_gen_configs():
    """
    Load global image generation configurations from YAML file.

    Returns:
        list: List of global image generation config dictionaries, or empty list
    """
    data = _global_config_data()
    if not data:
        return []

    try:
        configs = copy.deepcopy(data.get("global_image_generation_configs", []) or [])
        for cfg in configs:
            if isinstance(cfg, dict):
                cfg.setdefault("billing_tier", "free")
        return configs
    except Exception as e:
        print(f"Warning: Failed to load global image generation configs: {e}")
        return []


def load_global_vision_llm_configs():
    data = _global_config_data()
    if not data:
        return []

    try:
        configs = copy.deepcopy(data.get("global_vision_llm_configs", []) or [])
        for cfg in configs:
            if isinstance(cfg, dict):
                cfg.setdefault("billing_tier", "free")
        return configs
    except Exception as e:
        print(f"Warning: Failed to load global vision LLM configs: {e}")
        return []


def load_vision_llm_router_settings():
    default_settings = {
        "routing_strategy": "usage-based-routing",
        "num_retries": 3,
        "allowed_fails": 3,
        "cooldown_time": 60,
    }

    data = _global_config_data()
    if not data:
        return default_settings

    try:
        settings = data.get("vision_llm_router_settings", {})
        return {**default_settings, **settings}
    except Exception as e:
        print(f"Warning: Failed to load vision LLM router settings: {e}")
        return default_settings


def load_image_gen_router_settings():
    """
    Load router settings for image generation Auto mode from YAML file.

    Returns:
        dict: Router settings dictionary
    """
    default_settings = {
        "routing_strategy": "usage-based-routing",
        "num_retries": 3,
        "allowed_fails": 3,
        "cooldown_time": 60,
    }

    data = _global_config_data()
    if not data:
        return default_settings

    try:
        settings = data.get("image_generation_router_settings", {})
        return {**default_settings, **settings}
    except Exception as e:
        print(f"Warning: Failed to load image generation router settings: {e}")
        return default_settings


def load_openrouter_integration_settings() -> dict | None:
    """
    Load OpenRouter integration settings from the YAML config.

    Emits startup warnings for deprecated keys (``billing_tier``,
    ``anonymous_enabled``) and seeds their replacements for back-compat.

    Returns:
        dict with settings if present and enabled, None otherwise
    """
    data = _global_config_data()
    if not data:
        return None

    try:
        # Deep-copy so the setdefault back-compat seeding below never mutates
        # the cached YAML structure.
        settings = copy.deepcopy(data.get("openrouter_integration"))
        if not settings or not settings.get("enabled"):
            return None

        if "billing_tier" in settings:
            print(
                "Warning: openrouter_integration.billing_tier is deprecated; "
                "tier is now derived per model from OpenRouter data "
                "(':free' suffix or zero pricing). Remove this key."
            )

        if "anonymous_enabled" in settings:
            print(
                "Warning: openrouter_integration.anonymous_enabled is "
                "deprecated; use anonymous_enabled_paid and/or "
                "anonymous_enabled_free instead. Both new flags have been "
                "seeded from the legacy value for back-compat."
            )
            settings.setdefault("anonymous_enabled_paid", settings["anonymous_enabled"])
            settings.setdefault("anonymous_enabled_free", settings["anonymous_enabled"])

        # Image generation + vision LLM emission are opt-in (issue L).
        # OpenRouter's catalogue contains hundreds of image / vision
        # capable models; auto-injecting all of them into every
        # deployment would explode the model selector and surprise
        # operators upgrading from prior versions. Default to False so
        # admins must explicitly turn them on.
        settings.setdefault("image_generation_enabled", False)
        settings.setdefault("vision_enabled", False)

        return settings
    except Exception as e:
        print(f"Warning: Failed to load OpenRouter integration settings: {e}")
        return None


def initialize_openrouter_integration():
    """
    If enabled, fetch all OpenRouter models and append them to
    config.GLOBAL_LLM_CONFIGS as dynamic entries. Each model's ``billing_tier``
    is derived per-model from OpenRouter's API signals (``:free`` suffix or
    zero pricing), so free OpenRouter models correctly skip premium quota.

    Should be called BEFORE initialize_llm_router(). Dynamic entries are
    tagged ``router_pool_eligible=False`` so the LiteLLM Router pool (used
    by title-gen / sub-agent flows) remains scoped to curated YAML configs,
    while user-facing Auto-mode thread pinning still considers them.
    """
    settings = load_openrouter_integration_settings()
    if not settings:
        return

    try:
        from app.services.openrouter_integration_service import (
            OpenRouterIntegrationService,
        )

        service = OpenRouterIntegrationService.get_instance()
        new_configs = service.initialize(settings)

        if new_configs:
            config.GLOBAL_LLM_CONFIGS.extend(new_configs)
            free_count = sum(1 for c in new_configs if c.get("billing_tier") == "free")
            premium_count = sum(
                1 for c in new_configs if c.get("billing_tier") == "premium"
            )
            print(
                f"Info: OpenRouter integration added {len(new_configs)} models "
                f"(free={free_count}, premium={premium_count})"
            )
        else:
            print("Info: OpenRouter integration enabled but no models fetched")

        # Image generation + vision LLM emissions are opt-in (issue L).
        # Both reuse the catalogue already cached by ``service.initialize``
        # so we don't make additional network calls here.
        if settings.get("image_generation_enabled"):
            try:
                image_configs = service.get_image_generation_configs()
                if image_configs:
                    config.GLOBAL_IMAGE_GEN_CONFIGS.extend(image_configs)
                    print(
                        f"Info: OpenRouter integration added {len(image_configs)} "
                        f"image-generation models"
                    )
            except Exception as e:
                print(f"Warning: Failed to inject OpenRouter image-gen configs: {e}")

        if settings.get("vision_enabled"):
            try:
                vision_configs = service.get_vision_llm_configs()
                if vision_configs:
                    config.GLOBAL_VISION_LLM_CONFIGS.extend(vision_configs)
                    print(
                        f"Info: OpenRouter integration added {len(vision_configs)} "
                        f"vision LLM models"
                    )
            except Exception as e:
                print(f"Warning: Failed to inject OpenRouter vision-LLM configs: {e}")
    except Exception as e:
        print(f"Warning: Failed to initialize OpenRouter integration: {e}")


def initialize_pricing_registration():
    """
    Teach LiteLLM the per-token cost of every deployment in
    ``config.GLOBAL_LLM_CONFIGS`` (OpenRouter dynamic models pulled
    from the OpenRouter catalogue + any operator-declared YAML pricing).

    Must run AFTER ``initialize_openrouter_integration()`` so the
    OpenRouter catalogue is populated and BEFORE the first LLM call so
    ``response_cost`` is available in ``TokenTrackingCallback``.

    Failures are logged but never raised — startup must not be blocked
    by a missing pricing entry; the worst-case is the model debits 0.
    """
    try:
        from app.services.pricing_registration import (
            register_pricing_from_global_configs,
        )

        register_pricing_from_global_configs()
    except Exception as e:
        print(f"Warning: Failed to register LiteLLM pricing: {e}")


def initialize_llm_router():
    """
    Initialize the LLM Router service for Auto mode.
    This should be called during application startup, AFTER
    initialize_openrouter_integration() so dynamic models are included.
    Uses config.GLOBAL_LLM_CONFIGS (in-memory) which includes both
    static YAML configs and dynamic OpenRouter models.
    """
    all_configs = config.GLOBAL_LLM_CONFIGS
    # Reuse the router settings already parsed at Config construction instead
    # of re-reading the YAML here.
    router_settings = config.ROUTER_SETTINGS

    if not all_configs:
        print("Info: No global LLM configs found, Auto mode will not be available")
        return

    try:
        from app.services.llm_router_service import LLMRouterService

        LLMRouterService.initialize(all_configs, router_settings)
        print(
            f"Info: LLM Router initialized with {len(all_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})"
        )
    except Exception as e:
        print(f"Warning: Failed to initialize LLM Router: {e}")


def initialize_image_gen_router():
    """
    Initialize the Image Generation Router service for Auto mode.
    This should be called during application startup.
    """
    image_gen_configs = load_global_image_gen_configs()
    # Reuse the router settings already parsed at Config construction. The
    # *configs* list is intentionally re-read from YAML (it must exclude the
    # OpenRouter-injected dynamic models held in config.GLOBAL_IMAGE_GEN_CONFIGS).
    router_settings = config.IMAGE_GEN_ROUTER_SETTINGS

    if not image_gen_configs:
        print(
            "Info: No global image generation configs found, "
            "Image Generation Auto mode will not be available"
        )
        return

    try:
        from app.services.image_gen_router_service import ImageGenRouterService

        ImageGenRouterService.initialize(image_gen_configs, router_settings)
        print(
            f"Info: Image Generation Router initialized with {len(image_gen_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})"
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Image Generation Router: {e}")


def initialize_vision_llm_router():
    vision_configs = load_global_vision_llm_configs()
    # Reuse the router settings already parsed at Config construction. The
    # *configs* list is intentionally re-read from YAML (it must exclude the
    # OpenRouter-injected dynamic models held in config.GLOBAL_VISION_LLM_CONFIGS).
    router_settings = config.VISION_LLM_ROUTER_SETTINGS

    if not vision_configs:
        print(
            "Info: No global vision LLM configs found, "
            "Vision LLM Auto mode will not be available"
        )
        return

    try:
        from app.services.vision_llm_router_service import VisionLLMRouterService

        VisionLLMRouterService.initialize(vision_configs, router_settings)
        print(
            f"Info: Vision LLM Router initialized with {len(vision_configs)} models "
            f"(strategy: {router_settings.get('routing_strategy', 'usage-based-routing')})"
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Vision LLM Router: {e}")


class Config:
    # Check if ffmpeg is installed
    if not is_ffmpeg_installed():
        allow_static_ffmpeg = (
            os.getenv("SURFSENSE_ALLOW_STATIC_FFMPEG_DOWNLOAD", "TRUE").upper()
            == "TRUE"
        )
        if allow_static_ffmpeg:
            import static_ffmpeg

            # ffmpeg installed on first call to add_paths(), threadsafe.
            static_ffmpeg.add_paths()

        # check if ffmpeg is installed again
        if not is_ffmpeg_installed():
            raise ValueError(
                "FFmpeg is not installed on the system. Please install it to use the Surfsense Podcaster."
            )

    # Deployment Mode (self-hosted or cloud)
    # self-hosted: Full access to local file system connectors (Obsidian, etc.)
    # cloud: Only cloud-based connectors available
    DEPLOYMENT_MODE = os.getenv("SURFSENSE_DEPLOYMENT_MODE", "self-hosted")
    ENABLE_DESKTOP_LOCAL_FILESYSTEM = (
        os.getenv("ENABLE_DESKTOP_LOCAL_FILESYSTEM", "FALSE").upper() == "TRUE"
    )

    @classmethod
    def is_self_hosted(cls) -> bool:
        """Check if running in self-hosted mode."""
        return cls.DEPLOYMENT_MODE == "self-hosted"

    @classmethod
    def is_cloud(cls) -> bool:
        """Check if running in cloud mode."""
        return cls.DEPLOYMENT_MODE == "cloud"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Celery / Redis
    # Redis (single endpoint for Celery broker, result backend, and app cache).
    # Legacy CELERY_BROKER_URL / CELERY_RESULT_BACKEND / REDIS_APP_URL still
    # override individually when you need to split Redis across instances.
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")
    REDIS_APP_URL = os.getenv("REDIS_APP_URL", CELERY_BROKER_URL)
    CONNECTOR_INDEXING_LOCK_TTL_SECONDS = int(
        os.getenv("CONNECTOR_INDEXING_LOCK_TTL_SECONDS", str(8 * 60 * 60))
    )

    # Celery beat scheduling intervals (format: "<number><unit>", e.g. "2m", "1h")
    SCHEDULE_CHECKER_INTERVAL = os.getenv("SCHEDULE_CHECKER_INTERVAL", "2m")
    STRIPE_RECONCILIATION_INTERVAL = os.getenv("STRIPE_RECONCILIATION_INTERVAL", "10m")

    # File storage (local filesystem by default; Azure Blob optional)
    FILE_STORAGE_BACKEND = os.getenv("FILE_STORAGE_BACKEND", "local").strip().lower()
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
    FILE_STORAGE_LOCAL_PATH = os.getenv(
        "FILE_STORAGE_LOCAL_PATH", str(BASE_DIR / ".local_object_store")
    )

    # Daytona sandbox (code execution / filesystem sandbox)
    DAYTONA_SANDBOX_ENABLED = (
        os.getenv("DAYTONA_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"
    )
    DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
    DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api")
    DAYTONA_TARGET = os.getenv("DAYTONA_TARGET", "us")
    DAYTONA_SNAPSHOT_ID = os.getenv("DAYTONA_SNAPSHOT_ID") or None
    SANDBOX_FILES_DIR = os.getenv("SANDBOX_FILES_DIR", "sandbox_files")

    # Agent cache (in-process LRU+TTL cache for built agents)
    AGENT_CACHE_MAXSIZE = int(os.getenv("SURFSENSE_AGENT_CACHE_MAXSIZE", "256"))
    AGENT_CACHE_TTL_SECONDS = float(
        os.getenv("SURFSENSE_AGENT_CACHE_TTL_SECONDS", "1800")
    )

    # Connector discovery cache TTL
    CONNECTOR_DISCOVERY_TTL_SECONDS = float(
        os.getenv("SURFSENSE_CONNECTOR_DISCOVERY_TTL_SECONDS", "30")
    )

    # Platform web search (SearXNG)
    SEARXNG_DEFAULT_HOST = os.getenv("SEARXNG_DEFAULT_HOST")

    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL")
    # Backend URL to override the http to https in the OAuth redirect URI
    BACKEND_URL = os.getenv("BACKEND_URL")

    # Messaging gateway (Telegram v1)
    # Global master switch: when FALSE, no gateway supervisors/workers start and all
    # gateway HTTP routes return 404, regardless of the per-channel flags below.
    GATEWAY_ENABLED = os.getenv("GATEWAY_ENABLED", "TRUE").upper() == "TRUE"
    TELEGRAM_SHARED_BOT_TOKEN = os.getenv("TELEGRAM_SHARED_BOT_TOKEN")
    TELEGRAM_SHARED_BOT_USERNAME = os.getenv("TELEGRAM_SHARED_BOT_USERNAME")
    TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", BACKEND_URL)
    GATEWAY_TELEGRAM_INTAKE_MODE = os.getenv(
        "GATEWAY_TELEGRAM_INTAKE_MODE", "webhook"
    ).lower()
    if GATEWAY_TELEGRAM_INTAKE_MODE not in {"webhook", "longpoll", "disabled"}:
        raise ValueError(
            "GATEWAY_TELEGRAM_INTAKE_MODE must be one of: webhook, longpoll, disabled"
        )
    WHATSAPP_SHARED_BUSINESS_TOKEN = os.getenv("WHATSAPP_SHARED_BUSINESS_TOKEN")
    WHATSAPP_SHARED_PHONE_NUMBER_ID = os.getenv("WHATSAPP_SHARED_PHONE_NUMBER_ID")
    WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER = os.getenv(
        "WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER"
    )
    WHATSAPP_SHARED_WABA_ID = os.getenv("WHATSAPP_SHARED_WABA_ID")
    WHATSAPP_GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0")
    WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    WHATSAPP_WEBHOOK_APP_SECRET = os.getenv("WHATSAPP_WEBHOOK_APP_SECRET")
    WHATSAPP_BRIDGE_URL = os.getenv(
        "WHATSAPP_BRIDGE_URL", "http://whatsapp-bridge:9929"
    )
    GATEWAY_WHATSAPP_INTAKE_MODE = os.getenv(
        "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    ).lower()
    if GATEWAY_WHATSAPP_INTAKE_MODE not in {"cloud", "baileys", "disabled"}:
        raise ValueError(
            "GATEWAY_WHATSAPP_INTAKE_MODE must be one of: cloud, baileys, disabled"
        )
    GATEWAY_SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
    GATEWAY_SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
    GATEWAY_SLACK_ENABLED = (
        os.getenv("GATEWAY_SLACK_ENABLED", "FALSE").upper() == "TRUE"
    )
    GATEWAY_SLACK_SIGNING_SECRET = os.getenv("GATEWAY_SLACK_SIGNING_SECRET")
    GATEWAY_SLACK_REDIRECT_URI = os.getenv("GATEWAY_SLACK_REDIRECT_URI")
    GATEWAY_DISCORD_ENABLED = (
        os.getenv("GATEWAY_DISCORD_ENABLED", "FALSE").upper() == "TRUE"
    )
    GATEWAY_DISCORD_REDIRECT_URI = os.getenv("GATEWAY_DISCORD_REDIRECT_URI")

    # Stripe checkout (shared secrets for the unified credit wallet)
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_RECONCILIATION_LOOKBACK_MINUTES = int(
        os.getenv("STRIPE_RECONCILIATION_LOOKBACK_MINUTES", "10")
    )
    STRIPE_RECONCILIATION_BATCH_SIZE = int(
        os.getenv("STRIPE_RECONCILIATION_BATCH_SIZE", "100")
    )

    # Unified credit wallet (micro-USD) settings.
    #
    # Storage unit is integer micro-USD (1_000_000 = $1.00). A single
    # ``credit_micros_balance`` funds both ETL page processing and premium
    # model calls. New users start with ``DEFAULT_CREDIT_MICROS_BALANCE``
    # ($5 by default).
    #
    # Legacy env names (``PREMIUM_CREDIT_MICROS_LIMIT`` / ``PREMIUM_TOKEN_LIMIT``,
    # ``STRIPE_PREMIUM_TOKEN_PRICE_ID``, ``STRIPE_CREDIT_MICROS_PER_UNIT`` /
    # ``STRIPE_TOKENS_PER_UNIT``, ``STRIPE_TOKEN_BUYING_ENABLED``) are still
    # honoured as fall-backs for one release; deprecation warnings fire below.
    DEFAULT_CREDIT_MICROS_BALANCE = int(
        os.getenv("DEFAULT_CREDIT_MICROS_BALANCE")
        or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
        or os.getenv("PREMIUM_TOKEN_LIMIT", "5000000")
    )
    STRIPE_CREDIT_PRICE_ID = os.getenv("STRIPE_CREDIT_PRICE_ID") or os.getenv(
        "STRIPE_PREMIUM_TOKEN_PRICE_ID"
    )
    STRIPE_CREDIT_MICROS_PER_UNIT = int(
        os.getenv("STRIPE_CREDIT_MICROS_PER_UNIT")
        or os.getenv("STRIPE_TOKENS_PER_UNIT", "1000000")
    )
    STRIPE_CREDIT_BUYING_ENABLED = (
        os.getenv("STRIPE_CREDIT_BUYING_ENABLED")
        or os.getenv("STRIPE_TOKEN_BUYING_ENABLED", "FALSE")
    ).upper() == "TRUE"

    # ETL page processing debits the credit wallet only when enabled. Defaults
    # to FALSE so self-hosted / OSS installs keep effectively-free ETL; hosted
    # deployments set this TRUE. 1 page == ``MICROS_PER_PAGE`` micro-USD.
    ETL_CREDIT_BILLING_ENABLED = (
        os.getenv("ETL_CREDIT_BILLING_ENABLED", "FALSE").upper() == "TRUE"
    )
    MICROS_PER_PAGE = int(os.getenv("MICROS_PER_PAGE", "1000"))

    # Low-balance WARNING threshold (micro-USD). Surfaced by the quota service
    # so the UI can nudge the user to top up / enable auto-reload. $0.50.
    CREDIT_LOW_BALANCE_WARNING_MICROS = int(
        os.getenv("CREDIT_LOW_BALANCE_WARNING_MICROS", "500000")
    )

    # Auto-reload (off-session Stripe top-up) feature flag and guards.
    AUTO_RELOAD_ENABLED = os.getenv("AUTO_RELOAD_ENABLED", "FALSE").upper() == "TRUE"
    # Minimum configurable reload amount (micro-USD). $1.00 to match pack pricing.
    AUTO_RELOAD_MIN_AMOUNT_MICROS = int(
        os.getenv("AUTO_RELOAD_MIN_AMOUNT_MICROS", "1000000")
    )
    # Cooldown so a burst of debits can't fire multiple charges (minutes).
    AUTO_RELOAD_COOLDOWN_MINUTES = int(os.getenv("AUTO_RELOAD_COOLDOWN_MINUTES", "10"))

    # Safety ceiling on the per-call premium reservation. ``stream_new_chat``
    # estimates an upper-bound cost from ``litellm.get_model_info`` x the
    # config's ``quota_reserve_tokens`` and clamps the result to this value
    # so a misconfigured "$1000/M" model can't lock the user's whole balance
    # on one call. Default $1.00 covers realistic worst-cases (Opus + 4K
    # reserve_tokens ≈ $0.36) with headroom.
    QUOTA_MAX_RESERVE_MICROS = int(os.getenv("QUOTA_MAX_RESERVE_MICROS", "1000000"))

    if (
        os.getenv("PREMIUM_TOKEN_LIMIT") or os.getenv("PREMIUM_CREDIT_MICROS_LIMIT")
    ) and not os.getenv("DEFAULT_CREDIT_MICROS_BALANCE"):
        print(
            "Warning: PREMIUM_TOKEN_LIMIT / PREMIUM_CREDIT_MICROS_LIMIT are "
            "deprecated; rename to DEFAULT_CREDIT_MICROS_BALANCE. The old keys "
            "will be removed in a future release."
        )
    if os.getenv("STRIPE_TOKENS_PER_UNIT") and not os.getenv(
        "STRIPE_CREDIT_MICROS_PER_UNIT"
    ):
        print(
            "Warning: STRIPE_TOKENS_PER_UNIT is deprecated; rename to "
            "STRIPE_CREDIT_MICROS_PER_UNIT (1:1 numerical mapping). "
            "The old key will be removed in a future release."
        )
    if os.getenv("STRIPE_PREMIUM_TOKEN_PRICE_ID") and not os.getenv(
        "STRIPE_CREDIT_PRICE_ID"
    ):
        print(
            "Warning: STRIPE_PREMIUM_TOKEN_PRICE_ID is deprecated; rename to "
            "STRIPE_CREDIT_PRICE_ID. The old key will be removed in a future "
            "release."
        )
    if os.getenv("STRIPE_TOKEN_BUYING_ENABLED") and not os.getenv(
        "STRIPE_CREDIT_BUYING_ENABLED"
    ):
        print(
            "Warning: STRIPE_TOKEN_BUYING_ENABLED is deprecated; rename to "
            "STRIPE_CREDIT_BUYING_ENABLED. The old key will be removed in a "
            "future release."
        )

    # Anonymous / no-login mode settings
    NOLOGIN_MODE_ENABLED = os.getenv("NOLOGIN_MODE_ENABLED", "FALSE").upper() == "TRUE"
    ANON_TOKEN_LIMIT = int(os.getenv("ANON_TOKEN_LIMIT", "500000"))
    ANON_TOKEN_WARNING_THRESHOLD = int(
        os.getenv("ANON_TOKEN_WARNING_THRESHOLD", "400000")
    )
    ANON_TOKEN_QUOTA_TTL_DAYS = int(os.getenv("ANON_TOKEN_QUOTA_TTL_DAYS", "30"))
    ANON_MAX_UPLOAD_SIZE_MB = int(os.getenv("ANON_MAX_UPLOAD_SIZE_MB", "5"))

    # Default quota reserve tokens when not specified per-model
    QUOTA_MAX_RESERVE_PER_CALL = int(os.getenv("QUOTA_MAX_RESERVE_PER_CALL", "8000"))

    # Per-image reservation (in micro-USD) used by ``billable_call`` for the
    # ``POST /image-generations`` endpoint when the global config does not
    # override it. $0.05 covers realistic worst-cases for current OpenAI /
    # OpenRouter image-gen pricing. Bypassed entirely for free configs.
    QUOTA_DEFAULT_IMAGE_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_IMAGE_RESERVE_MICROS", "50000")
    )

    # Per-podcast reservation (in micro-USD). One agent LLM call generating
    # a transcript, typically 5k-20k completion tokens. $0.20 covers a long
    # premium-model run. Tune via env.
    QUOTA_DEFAULT_PODCAST_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_PODCAST_RESERVE_MICROS", "200000")
    )

    # Per-video-presentation reservation (in micro-USD). Fan-out of N
    # slide-scene generations (up to ``VIDEO_PRESENTATION_MAX_SLIDES=30``)
    # plus refine retries; can produce many premium completions. $1.00
    # covers worst-case. Tune via env.
    #
    # NOTE: this equals the existing ``QUOTA_MAX_RESERVE_MICROS`` default of
    # 1_000_000. The override path in ``billable_call`` bypasses the
    # per-call clamp in ``estimate_call_reserve_micros``, so this is the
    # *actual* hold — raising it via env is fine but means a single video
    # task can lock $1+ of credit.
    QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS = int(
        os.getenv("QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS", "1000000")
    )

    # Abuse prevention: concurrent stream cap and CAPTCHA
    ANON_MAX_CONCURRENT_STREAMS = int(os.getenv("ANON_MAX_CONCURRENT_STREAMS", "2"))
    ANON_CAPTCHA_REQUEST_THRESHOLD = int(
        os.getenv("ANON_CAPTCHA_REQUEST_THRESHOLD", "5")
    )

    # Cloudflare Turnstile CAPTCHA
    TURNSTILE_ENABLED = os.getenv("TURNSTILE_ENABLED", "FALSE").upper() == "TRUE"
    TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

    # Auth
    AUTH_TYPE = os.getenv("AUTH_TYPE")
    REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "TRUE").upper() == "TRUE"

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_PICKER_API_KEY = os.getenv("GOOGLE_PICKER_API_KEY")

    # Google Calendar redirect URI
    GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI")

    # Google Gmail redirect URI
    GOOGLE_GMAIL_REDIRECT_URI = os.getenv("GOOGLE_GMAIL_REDIRECT_URI")

    # Google Drive redirect URI
    GOOGLE_DRIVE_REDIRECT_URI = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")

    # Airtable OAuth
    AIRTABLE_CLIENT_ID = os.getenv("AIRTABLE_CLIENT_ID")
    AIRTABLE_CLIENT_SECRET = os.getenv("AIRTABLE_CLIENT_SECRET")
    AIRTABLE_REDIRECT_URI = os.getenv("AIRTABLE_REDIRECT_URI")

    # Notion OAuth
    NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
    NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
    NOTION_REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI")

    # Atlassian OAuth (shared for Jira and Confluence)
    ATLASSIAN_CLIENT_ID = os.getenv("ATLASSIAN_CLIENT_ID")
    ATLASSIAN_CLIENT_SECRET = os.getenv("ATLASSIAN_CLIENT_SECRET")
    JIRA_REDIRECT_URI = os.getenv("JIRA_REDIRECT_URI")
    CONFLUENCE_REDIRECT_URI = os.getenv("CONFLUENCE_REDIRECT_URI")

    # Linear OAuth
    LINEAR_CLIENT_ID = os.getenv("LINEAR_CLIENT_ID")
    LINEAR_CLIENT_SECRET = os.getenv("LINEAR_CLIENT_SECRET")
    LINEAR_REDIRECT_URI = os.getenv("LINEAR_REDIRECT_URI")

    # Slack OAuth
    SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")

    # Discord OAuth
    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
    DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    # Microsoft OAuth (shared for Teams and OneDrive)
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
    TEAMS_REDIRECT_URI = os.getenv("TEAMS_REDIRECT_URI")
    ONEDRIVE_REDIRECT_URI = os.getenv("ONEDRIVE_REDIRECT_URI")

    # ClickUp OAuth
    CLICKUP_CLIENT_ID = os.getenv("CLICKUP_CLIENT_ID")
    CLICKUP_CLIENT_SECRET = os.getenv("CLICKUP_CLIENT_SECRET")
    CLICKUP_REDIRECT_URI = os.getenv("CLICKUP_REDIRECT_URI")

    # Dropbox OAuth
    DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
    DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
    DROPBOX_REDIRECT_URI = os.getenv("DROPBOX_REDIRECT_URI")

    # Composio Configuration (for managed OAuth integrations)
    # Get your API key from https://app.composio.dev
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
    COMPOSIO_ENABLED = os.getenv("COMPOSIO_ENABLED", "FALSE").upper() == "TRUE"
    COMPOSIO_REDIRECT_URI = os.getenv("COMPOSIO_REDIRECT_URI")

    # LLM instances are now managed per-user through the LLMConfig system
    # Legacy environment variables removed in favor of user-specific configurations

    # Global LLM Configurations (optional)
    # Load from global_llm_config.yaml if available
    # These can be used as default options for users
    GLOBAL_LLM_CONFIGS = load_global_llm_configs()

    # Router settings for Auto mode (LiteLLM Router load balancing)
    ROUTER_SETTINGS = load_router_settings()

    # Global Image Generation Configurations (optional)
    GLOBAL_IMAGE_GEN_CONFIGS = load_global_image_gen_configs()

    # Router settings for Image Generation Auto mode
    IMAGE_GEN_ROUTER_SETTINGS = load_image_gen_router_settings()

    # Global Vision LLM Configurations (optional)
    GLOBAL_VISION_LLM_CONFIGS = load_global_vision_llm_configs()

    # Router settings for Vision LLM Auto mode
    VISION_LLM_ROUTER_SETTINGS = load_vision_llm_router_settings()

    # OpenRouter Integration settings (optional)
    OPENROUTER_INTEGRATION_SETTINGS = load_openrouter_integration_settings()

    # Chonkie Configuration | Edit this to your needs
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    # Azure OpenAI credentials from environment variables
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    # Pass Azure credentials to embeddings when using Azure OpenAI
    embedding_kwargs = {}
    if AZURE_OPENAI_ENDPOINT:
        embedding_kwargs["azure_endpoint"] = AZURE_OPENAI_ENDPOINT
    if AZURE_OPENAI_API_KEY:
        embedding_kwargs["azure_api_key"] = AZURE_OPENAI_API_KEY

    embedding_model_instance = AutoEmbeddings.get_embeddings(
        EMBEDDING_MODEL,
        **embedding_kwargs,
    )
    is_local_embedding_model = "://" not in (EMBEDDING_MODEL or "")
    chunker_instance = RecursiveChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )
    code_chunker_instance = CodeChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )

    # Reranker's Configuration | Pinecone, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
    RERANKERS_ENABLED = os.getenv("RERANKERS_ENABLED", "FALSE").upper() == "TRUE"
    if RERANKERS_ENABLED:
        RERANKERS_MODEL_NAME = os.getenv("RERANKERS_MODEL_NAME")
        RERANKERS_MODEL_TYPE = os.getenv("RERANKERS_MODEL_TYPE")
        reranker_instance = Reranker(
            model_name=RERANKERS_MODEL_NAME,
            model_type=RERANKERS_MODEL_TYPE,
        )
    else:
        reranker_instance = None

    # OAuth JWT
    SECRET_KEY = os.getenv("SECRET_KEY")

    # JWT Token Lifetimes
    ACCESS_TOKEN_LIFETIME_SECONDS = int(
        os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", str(24 * 60 * 60))  # 1 day
    )
    REFRESH_TOKEN_LIFETIME_SECONDS = int(
        os.getenv("REFRESH_TOKEN_LIFETIME_SECONDS", str(14 * 24 * 60 * 60))  # 2 weeks
    )

    # ETL Service
    ETL_SERVICE = os.getenv("ETL_SERVICE")

    if ETL_SERVICE == "UNSTRUCTURED":
        # Unstructured API Key
        UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")

    elif ETL_SERVICE == "LLAMACLOUD":
        LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
        # Optional: Azure Document Intelligence accelerator for supported file types
        AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
        AZURE_DI_KEY = os.getenv("AZURE_DI_KEY")

    # ETL parse cache: reuse parser output for identical bytes across workspaces.
    ETL_CACHE_ENABLED = os.getenv("ETL_CACHE_ENABLED", "false").strip().lower() == "true"
    # Bump to invalidate every cached entry after a parser/behaviour change.
    ETL_CACHE_PARSER_VERSION = int(os.getenv("ETL_CACHE_PARSER_VERSION", "1"))
    ETL_CACHE_TTL_DAYS = int(os.getenv("ETL_CACHE_TTL_DAYS", "90"))
    ETL_CACHE_MAX_TOTAL_MB = int(os.getenv("ETL_CACHE_MAX_TOTAL_MB", "5120"))
    ETL_CACHE_EVICTION_BATCH = int(os.getenv("ETL_CACHE_EVICTION_BATCH", "500"))
    # Optional dedicated blob storage; unset reuses the main file_storage backend.
    ETL_CACHE_STORAGE_BACKEND = os.getenv("ETL_CACHE_STORAGE_BACKEND")
    ETL_CACHE_STORAGE_CONTAINER = os.getenv("ETL_CACHE_STORAGE_CONTAINER")
    ETL_CACHE_STORAGE_LOCAL_PATH = os.getenv("ETL_CACHE_STORAGE_LOCAL_PATH")

    # Embedding cache: reuse chunk+embedding output for identical markdown across
    # workspaces. Blobs share the ETL_CACHE_STORAGE_* backend.
    EMBEDDING_CACHE_ENABLED = (
        os.getenv("EMBEDDING_CACHE_ENABLED", "false").strip().lower() == "true"
    )
    # Bump to invalidate every cached embedding set after a chunker change.
    EMBEDDING_CACHE_CHUNKER_VERSION = int(
        os.getenv("EMBEDDING_CACHE_CHUNKER_VERSION", "1")
    )
    EMBEDDING_CACHE_TTL_DAYS = int(os.getenv("EMBEDDING_CACHE_TTL_DAYS", "90"))
    EMBEDDING_CACHE_MAX_TOTAL_MB = int(os.getenv("EMBEDDING_CACHE_MAX_TOTAL_MB", "5120"))
    EMBEDDING_CACHE_EVICTION_BATCH = int(
        os.getenv("EMBEDDING_CACHE_EVICTION_BATCH", "500")
    )

    # Incremental re-indexing: on document edits, keep chunk rows whose text is
    # unchanged (reusing their embeddings) and embed only new/changed chunks.
    # Kill switch -- disabling falls back to delete-all + full re-embed.
    CHUNK_RECONCILE_ENABLED = (
        os.getenv("CHUNK_RECONCILE_ENABLED", "true").strip().lower() == "true"
    )

    # Proxy provider selection. Maps to a ProxyProvider implementation registered
    # in app/utils/proxy/registry.py. Add new vendors there and switch via this var.
    PROXY_PROVIDER = os.getenv("PROXY_PROVIDER", "anonymous_proxies")

    # Residential Proxy Configuration (anonymous-proxies.net)
    # Used for web crawling and YouTube transcript fetching to avoid IP bans.
    # Consumed by the "anonymous_proxies" proxy provider.
    RESIDENTIAL_PROXY_USERNAME = os.getenv("RESIDENTIAL_PROXY_USERNAME")
    RESIDENTIAL_PROXY_PASSWORD = os.getenv("RESIDENTIAL_PROXY_PASSWORD")
    RESIDENTIAL_PROXY_HOSTNAME = os.getenv("RESIDENTIAL_PROXY_HOSTNAME")
    RESIDENTIAL_PROXY_LOCATION = os.getenv("RESIDENTIAL_PROXY_LOCATION", "")
    RESIDENTIAL_PROXY_TYPE = int(os.getenv("RESIDENTIAL_PROXY_TYPE", "1"))

    # Litellm TTS Configuration
    TTS_SERVICE = os.getenv("TTS_SERVICE")
    TTS_SERVICE_API_BASE = os.getenv("TTS_SERVICE_API_BASE")
    TTS_SERVICE_API_KEY = os.getenv("TTS_SERVICE_API_KEY")

    # STT Configuration
    STT_SERVICE = os.getenv("STT_SERVICE")
    STT_SERVICE_API_BASE = os.getenv("STT_SERVICE_API_BASE")
    STT_SERVICE_API_KEY = os.getenv("STT_SERVICE_API_KEY")

    # Video presentation defaults
    VIDEO_PRESENTATION_MAX_SLIDES = int(
        os.getenv("VIDEO_PRESENTATION_MAX_SLIDES", "30")
    )
    VIDEO_PRESENTATION_FPS = int(os.getenv("VIDEO_PRESENTATION_FPS", "30"))
    VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES = int(
        os.getenv("VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES", "300")
    )

    # Validation Checks
    # Check embedding dimension
    if (
        hasattr(embedding_model_instance, "dimension")
        and embedding_model_instance.dimension > 2000
    ):
        raise ValueError(
            f"Embedding dimension for Model: {EMBEDDING_MODEL} "
            f"has {embedding_model_instance.dimension} dimensions, which "
            f"exceeds the maximum of 2000 allowed by PGVector."
        )

    @classmethod
    def get_settings(cls):
        """Get all settings as a dictionary."""
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }


# Create a config instance
config = Config()
