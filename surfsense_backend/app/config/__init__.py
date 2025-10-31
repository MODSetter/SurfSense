import os
import shutil
from pathlib import Path
from typing import Any

from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from chonkie.embeddings.azure_openai import AzureOpenAIEmbeddings
from chonkie.embeddings.registry import EmbeddingsRegistry
from dotenv import load_dotenv
from rerankers import Reranker


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
        batch_size: int = 128,
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


def is_ffmpeg_installed():
    """
    Check if ffmpeg is installed on the current system.

    Returns:
        bool: True if ffmpeg is installed, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


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
    chunker_instance = RecursiveChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )
    code_chunker_instance = CodeChunker(
        chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
    )

    # Reranker's Configuration | Pinecode, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
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
