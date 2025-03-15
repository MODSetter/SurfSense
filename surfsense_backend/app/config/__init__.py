import os
from pathlib import Path

from chonkie import AutoEmbeddings, LateChunker
from rerankers import Reranker
from langchain_community.chat_models import ChatLiteLLM


from dotenv import load_dotenv

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env_file = BASE_DIR / ".env"
load_dotenv(env_file)


def extract_model_name(llm_string: str) -> str:
    """Extract the model name from an LLM string.
    Example: "litellm:openai/gpt-4o-mini" -> "openai/gpt-4o-mini"
    
    Args:
        llm_string: The LLM string with optional prefix
        
    Returns:
        str: The extracted model name
    """
    return llm_string.split(":", 1)[1] if ":" in llm_string else llm_string

class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL")
    
    # LONG-CONTEXT LLMS
    LONG_CONTEXT_LLM = os.getenv("LONG_CONTEXT_LLM")
    long_context_llm_instance = ChatLiteLLM(model=extract_model_name(LONG_CONTEXT_LLM))
    
    # GPT Researcher
    FAST_LLM = os.getenv("FAST_LLM")
    SMART_LLM = os.getenv("SMART_LLM")
    STRATEGIC_LLM = os.getenv("STRATEGIC_LLM")
    fast_llm_instance = ChatLiteLLM(model=extract_model_name(FAST_LLM))
    smart_llm_instance = ChatLiteLLM(model=extract_model_name(SMART_LLM))
    strategic_llm_instance = ChatLiteLLM(model=extract_model_name(STRATEGIC_LLM))
    

    # Chonkie Configuration | Edit this to your needs
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    embedding_model_instance = AutoEmbeddings.get_embeddings(EMBEDDING_MODEL)
    chunker_instance = LateChunker(
        embedding_model=EMBEDDING_MODEL,
        chunk_size=embedding_model_instance.max_seq_length,
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
    
    # Unstructured API Key
    UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY")
    
    # Firecrawl API Key
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", None) 
    
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
