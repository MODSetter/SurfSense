import os
from pathlib import Path
import shutil

from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from dotenv import load_dotenv

from rerankers import Reranker


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
            raise ValueError("FFmpeg is not installed on the system. Please install it to use the Surfsense Podcaster.")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL")
    
    
    # AUTH: Google OAuth
    AUTH_TYPE = os.getenv("AUTH_TYPE")
    if AUTH_TYPE == "GOOGLE":
        GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        
    
    # LLM instances are now managed per-user through the LLMConfig system
    # Legacy environment variables removed in favor of user-specific configurations

    # Chonkie Configuration | Edit this to your needs
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    embedding_model_instance = AutoEmbeddings.get_embeddings(EMBEDDING_MODEL)
    chunker_instance = RecursiveChunker(
        chunk_size=getattr(embedding_model_instance, 'max_seq_length', 512)
    )
    code_chunker_instance = CodeChunker(
        chunk_size=getattr(embedding_model_instance, 'max_seq_length', 512)
    )
    
    # Reranker's Configuration | Pinecode, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
    RERANKERS_MODEL_NAME = os.getenv("RERANKERS_MODEL_NAME")
    RERANKERS_MODEL_TYPE = os.getenv("RERANKERS_MODEL_TYPE")
    reranker_instance = Reranker(
        model_name=RERANKERS_MODEL_NAME,
        model_type=RERANKERS_MODEL_TYPE,
    )
    
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
    
    # Litellm STT Configuration
    STT_SERVICE = os.getenv("STT_SERVICE")
    STT_SERVICE_API_BASE = os.getenv("STT_SERVICE_API_BASE")
    STT_SERVICE_API_KEY = os.getenv("STT_SERVICE_API_KEY")
    
    
    # Validation Checks
    # Check embedding dimension
    if hasattr(embedding_model_instance, 'dimension') and embedding_model_instance.dimension > 2000:
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
