import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any

import yaml
from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from chonkie.embeddings.azure_openai import AzureOpenAIEmbeddings
from chonkie.embeddings.registry import EmbeddingsRegistry
from dotenv import load_dotenv
from rerankers import Reranker

from app.config.secrets_loader import inject_secrets_to_env


# Monkey patch AzureOpenAIEmbeddings to fix parameter order issue
# This is a temporary workaround until the upstream chonkie library is fixed
class FixedAzureOpenAIEmbeddings(AzureOpenAIEmbeddings):
    """Wrapper around AzureOpenAIEmbeddings with fixed parameter order."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        azure_endpoint: str | None = None,
        tokenizer: Any | None = None,
        dimension: int | None = None,
        azure_api_key: str | None = None,
        api_version: str = "2024-10-21",
        deployment: str | None = None,
        max_retries: int = 3,
        timeout: float = 60.0,
        batch_size: int = 32,  # Reduced from 128 to save RAM
        **kwargs: dict[str, Any],
    ):
        """Initialize with model as first parameter to avoid conflicts."""
        # Call parent's __init__ by explicitly passing azure_endpoint as first arg
        # to maintain compatibility with the original signature
        super().__init__(
            azure_endpoint=azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            model=model,
            tokenizer=tokenizer,
            dimension=dimension,
            azure_api_key=azure_api_key,
            api_version=api_version,
            deployment=deployment,
            max_retries=max_retries,
            timeout=timeout,
            batch_size=batch_size,
            **kwargs,
        )


# TODO: Fix this in chonkie upstream
# Register our fixed Azure OpenAI embeddings with pattern
# This automatically infers the following arguments from their corresponding environment variables if they are not provided:
# - `api_key` from `AZURE_OPENAI_API_KEY`
# - `organization` from `OPENAI_ORG_ID`
# - `project` from `OPENAI_PROJECT_ID`
# - `azure_ad_token` from `AZURE_OPENAI_AD_TOKEN`
# - `api_version` from `OPENAI_API_VERSION`
# - `azure_endpoint` from `AZURE_OPENAI_ENDPOINT`
EmbeddingsRegistry.register_provider("azure_openai", FixedAzureOpenAIEmbeddings)
EmbeddingsRegistry.register_pattern(r"^text-embedding-", FixedAzureOpenAIEmbeddings)
EmbeddingsRegistry.register_model("text-embedding-ada-002", FixedAzureOpenAIEmbeddings)
EmbeddingsRegistry.register_model("text-embedding-3-small", FixedAzureOpenAIEmbeddings)
EmbeddingsRegistry.register_model("text-embedding-3-large", FixedAzureOpenAIEmbeddings)


# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env_file = BASE_DIR / ".env"
load_dotenv(env_file)

# Load and inject SOPS-encrypted secrets into environment
# This allows secrets from secrets.enc.yaml to override/supplement .env values
# Priority: SOPS secrets > .env file > system environment
inject_secrets_to_env()


def is_ffmpeg_installed():
    """
    Check if ffmpeg is installed on the current system.

    Returns:
        bool: True if ffmpeg is installed, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


def expand_env_vars(data):
    """
    Recursively expand environment variables in data structure.
    Supports ${VAR_NAME} syntax for environment variable substitution.

    Args:
        data: Dictionary, list, string, or other data type

    Returns:
        Data with environment variables expanded

    Example:
        >>> os.environ['API_KEY'] = 'secret123'
        >>> expand_env_vars({'key': '${API_KEY}'})
        {'key': 'secret123'}
    """
    if isinstance(data, dict):
        return {key: expand_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Replace ${VAR_NAME} with environment variable value
        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))  # Keep original if not found
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, data)
    else:
        return data


def load_global_llm_configs():
    """
    Load global LLM configurations from YAML file with environment variable expansion.
    Falls back to example file if main file doesn't exist.

    Environment variables in the format ${VAR_NAME} will be automatically expanded
    to their values from the environment. This allows secure storage of API keys
    in .env files instead of hardcoding them in the YAML configuration.

    Returns:
        list: List of global LLM config dictionaries with env vars expanded,
              or empty list if file doesn't exist

    Example:
        In global_llm_config.yaml:
            api_key: "${GEMINI_API_KEY}"
        In .env:
            GEMINI_API_KEY=actual-key-value
        Result:
            api_key: "actual-key-value"
    """
    # Try main config file first
    global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.yaml"

    # Fall back to example file for testing
    # if not global_config_file.exists():
    #     global_config_file = BASE_DIR / "app" / "config" / "global_llm_config.example.yaml"
    #     if global_config_file.exists():
    #         print("Info: Using global_llm_config.example.yaml (copy to global_llm_config.yaml for production)")

    if not global_config_file.exists():
        # No global configs available
        return []

    try:
        with open(global_config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            configs = data.get("global_llm_configs", [])
            # Expand environment variables in the configuration
            return expand_env_vars(configs)
    except Exception as e:
        print(f"Warning: Failed to load global LLM configs: {e}")
        return []


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

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL")
    # Backend URL to override the http to https in the OAuth redirect URI
    BACKEND_URL = os.getenv("BACKEND_URL")

    # Auth
    AUTH_TYPE = os.getenv("AUTH_TYPE")
    REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "TRUE").upper() == "TRUE"

    # CORS Configuration
    # Comma-separated list of allowed origins, defaults to frontend URL
    # Note: Wildcard "*" is not allowed when allow_credentials=True
    _default_cors_origin = os.getenv("NEXT_FRONTEND_URL", "http://localhost:3000")
    _cors_origins_str = os.getenv("CORS_ORIGINS", _default_cors_origin)
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]

    # Site Configuration Defaults
    DEFAULT_CONTACT_EMAIL = os.getenv("DEFAULT_CONTACT_EMAIL", "support@example.com")

    # Trusted proxy hosts for ProxyHeadersMiddleware
    # Comma-separated list of trusted proxy IPs/hosts
    # SECURITY: Set this to your actual proxy IPs in production
    _trusted_hosts_str = os.getenv("TRUSTED_HOSTS", "127.0.0.1")
    TRUSTED_HOSTS = [host.strip() for host in _trusted_hosts_str.split(",") if host.strip()]

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    # Google Calendar redirect URI
    GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI")

    # Google Gmail redirect URI
    GOOGLE_GMAIL_REDIRECT_URI = os.getenv("GOOGLE_GMAIL_REDIRECT_URI")

    # Airtable OAuth
    AIRTABLE_CLIENT_ID = os.getenv("AIRTABLE_CLIENT_ID")
    AIRTABLE_CLIENT_SECRET = os.getenv("AIRTABLE_CLIENT_SECRET")
    AIRTABLE_REDIRECT_URI = os.getenv("AIRTABLE_REDIRECT_URI")

    # LLM instances are now managed per-user through the LLMConfig system
    # Legacy environment variables removed in favor of user-specific configurations

    # Global LLM Configurations (optional)
    # Load from global_llm_config.yaml if available
    # These can be used as default options for users
    GLOBAL_LLM_CONFIGS = load_global_llm_configs()

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

    # Lazy-loaded model instances (initialized on first access to save RAM)
    _embedding_model_instance = None
    _chunker_instance = None
    _code_chunker_instance = None
    _reranker_instance = None
    _init_lock = threading.RLock()  # Reentrant lock for nested initialization calls

    @classmethod
    def _initialize_embedding_model(cls):
        """Initialize embedding model on first access (lazy loading with thread-safety)."""
        if cls._embedding_model_instance is None:
            with cls._init_lock:
                # Double-check after acquiring lock
                if cls._embedding_model_instance is None:
                    cls._embedding_model_instance = AutoEmbeddings.get_embeddings(
                        cls.EMBEDDING_MODEL,
                        **cls.embedding_kwargs,
                    )
                    # Validate embedding dimension
                    if (
                        hasattr(cls._embedding_model_instance, "dimension")
                        and cls._embedding_model_instance.dimension > 2000
                    ):
                        raise ValueError(
                            f"Embedding dimension for Model: {cls.EMBEDDING_MODEL} "
                            f"has {cls._embedding_model_instance.dimension} dimensions, which "
                            f"exceeds the maximum of 2000 allowed by PGVector."
                        )
        return cls._embedding_model_instance

    @classmethod
    def _initialize_chunker(cls):
        """Initialize chunker on first access (lazy loading with thread-safety)."""
        if cls._chunker_instance is None:
            with cls._init_lock:
                # Double-check after acquiring lock
                if cls._chunker_instance is None:
                    embedding_model = cls._initialize_embedding_model()
                    cls._chunker_instance = RecursiveChunker(
                        chunk_size=getattr(embedding_model, "max_seq_length", 512)
                    )
        return cls._chunker_instance

    @classmethod
    def _initialize_code_chunker(cls):
        """Initialize code chunker on first access (lazy loading with thread-safety)."""
        if cls._code_chunker_instance is None:
            with cls._init_lock:
                # Double-check after acquiring lock
                if cls._code_chunker_instance is None:
                    embedding_model = cls._initialize_embedding_model()
                    cls._code_chunker_instance = CodeChunker(
                        chunk_size=getattr(embedding_model, "max_seq_length", 512)
                    )
        return cls._code_chunker_instance

    # Properties for lazy access to model instances
    @property
    def embedding_model_instance(self):
        return Config._initialize_embedding_model()

    @property
    def chunker_instance(self):
        return Config._initialize_chunker()

    @property
    def code_chunker_instance(self):
        return Config._initialize_code_chunker()

    # Reranker's Configuration | Pinecode, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
    RERANKERS_ENABLED = os.getenv("RERANKERS_ENABLED", "FALSE").upper() == "TRUE"
    RERANKERS_MODEL_NAME = os.getenv("RERANKERS_MODEL_NAME") if RERANKERS_ENABLED else None
    RERANKERS_MODEL_TYPE = os.getenv("RERANKERS_MODEL_TYPE") if RERANKERS_ENABLED else None

    @classmethod
    def _initialize_reranker(cls):
        """Initialize reranker on first access (lazy loading with thread-safety)."""
        if not cls.RERANKERS_ENABLED:
            return None
        if cls._reranker_instance is None:
            with cls._init_lock:
                # Double-check after acquiring lock
                if cls._reranker_instance is None:
                    cls._reranker_instance = Reranker(
                        model_name=cls.RERANKERS_MODEL_NAME,
                        model_type=cls.RERANKERS_MODEL_TYPE,
                    )
        return cls._reranker_instance

    @property
    def reranker_instance(self):
        return Config._initialize_reranker()

    # OAuth JWT
    SECRET_KEY = os.getenv("SECRET_KEY")

    # ETL Service
    ETL_SERVICE = os.getenv("ETL_SERVICE")

    if ETL_SERVICE == "UNSTRUCTURED":
        # Unstructured API Key
        UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")

    elif ETL_SERVICE == "LLAMACLOUD":
        # LlamaCloud API Key
        LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

    # Firecrawl API Key
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", None)

    # Litellm TTS Configuration
    TTS_SERVICE = os.getenv("TTS_SERVICE")
    TTS_SERVICE_API_BASE = os.getenv("TTS_SERVICE_API_BASE")
    TTS_SERVICE_API_KEY = os.getenv("TTS_SERVICE_API_KEY")

    # STT Configuration
    STT_SERVICE = os.getenv("STT_SERVICE")
    STT_SERVICE_API_BASE = os.getenv("STT_SERVICE_API_BASE")
    STT_SERVICE_API_KEY = os.getenv("STT_SERVICE_API_KEY")

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
