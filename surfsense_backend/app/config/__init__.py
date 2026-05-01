import os
import shutil
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
    # Try main config file first
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        # No global configs available
        return []

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            configs = data.get("global_llm_configs", [])

        seen_slugs: dict[str, int] = {}
        for cfg in configs:
            cfg.setdefault("billing_tier", "free")
            cfg.setdefault("anonymous_enabled", False)
            cfg.setdefault("seo_enabled", False)

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

    # Try main config file first
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return default_settings

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
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
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return []

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("global_image_generation_configs", [])
    except Exception as e:
        print(f"Warning: Failed to load global image generation configs: {e}")
        return []


def load_global_vision_llm_configs():
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return []

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("global_vision_llm_configs", [])
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

    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return default_settings

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
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

    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return default_settings

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
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
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    if not global_config_file.exists():
        return None

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            settings = data.get("openrouter_integration")
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
                settings.setdefault(
                    "anonymous_enabled_paid", settings["anonymous_enabled"]
                )
                settings.setdefault(
                    "anonymous_enabled_free", settings["anonymous_enabled"]
                )

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
    except Exception as e:
        print(f"Warning: Failed to initialize OpenRouter integration: {e}")


def initialize_llm_router():
    """
    Initialize the LLM Router service for Auto mode.
    This should be called during application startup, AFTER
    initialize_openrouter_integration() so dynamic models are included.
    Uses config.GLOBAL_LLM_CONFIGS (in-memory) which includes both
    static YAML configs and dynamic OpenRouter models.
    """
    all_configs = config.GLOBAL_LLM_CONFIGS
    router_settings = load_router_settings()

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
    router_settings = load_image_gen_router_settings()

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
    router_settings = load_vision_llm_router_settings()

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
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )
    CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")
    REDIS_APP_URL = os.getenv("REDIS_APP_URL", CELERY_BROKER_URL)
    CONNECTOR_INDEXING_LOCK_TTL_SECONDS = int(
        os.getenv("CONNECTOR_INDEXING_LOCK_TTL_SECONDS", str(8 * 60 * 60))
    )

    # Platform web search (SearXNG)
    SEARXNG_DEFAULT_HOST = os.getenv("SEARXNG_DEFAULT_HOST")

    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL")
    # Backend URL to override the http to https in the OAuth redirect URI
    BACKEND_URL = os.getenv("BACKEND_URL")

    # Stripe checkout for pay-as-you-go page packs
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
    STRIPE_PAGES_PER_UNIT = int(os.getenv("STRIPE_PAGES_PER_UNIT", "1000"))
    STRIPE_PAGE_BUYING_ENABLED = (
        os.getenv("STRIPE_PAGE_BUYING_ENABLED", "TRUE").upper() == "TRUE"
    )
    STRIPE_RECONCILIATION_LOOKBACK_MINUTES = int(
        os.getenv("STRIPE_RECONCILIATION_LOOKBACK_MINUTES", "10")
    )
    STRIPE_RECONCILIATION_BATCH_SIZE = int(
        os.getenv("STRIPE_RECONCILIATION_BATCH_SIZE", "100")
    )

    # Premium token quota settings
    PREMIUM_TOKEN_LIMIT = int(os.getenv("PREMIUM_TOKEN_LIMIT", "3000000"))
    STRIPE_PREMIUM_TOKEN_PRICE_ID = os.getenv("STRIPE_PREMIUM_TOKEN_PRICE_ID")
    STRIPE_TOKENS_PER_UNIT = int(os.getenv("STRIPE_TOKENS_PER_UNIT", "1000000"))
    STRIPE_TOKEN_BUYING_ENABLED = (
        os.getenv("STRIPE_TOKEN_BUYING_ENABLED", "FALSE").upper() == "TRUE"
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

    # Pages limit for ETL services (default to very high number for OSS unlimited usage)
    PAGES_LIMIT = int(os.getenv("PAGES_LIMIT", "999999999"))

    if ETL_SERVICE == "UNSTRUCTURED":
        # Unstructured API Key
        UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")

    elif ETL_SERVICE == "LLAMACLOUD":
        LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
        # Optional: Azure Document Intelligence accelerator for supported file types
        AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
        AZURE_DI_KEY = os.getenv("AZURE_DI_KEY")

    # Residential Proxy Configuration (anonymous-proxies.net)
    # Used for web crawling and YouTube transcript fetching to avoid IP bans.
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
