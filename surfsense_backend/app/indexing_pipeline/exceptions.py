from litellm.exceptions import (
    APIConnectionError,
    APIResponseValidationError,
    AuthenticationError,
    BadGatewayError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    UnprocessableEntityError,
)
from sqlalchemy.exc import IntegrityError as IntegrityError

from app.services.llm_error_adapter import LLMErrorCategory, adapt_llm_exception

# Tuples for use directly in except clauses.
RETRYABLE_LLM_ERRORS = (
    RateLimitError,
    Timeout,
    ServiceUnavailableError,
    BadGatewayError,
    InternalServerError,
    APIConnectionError,
)

PERMANENT_LLM_ERRORS = (
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    APIResponseValidationError,
)

# (LiteLLMEmbeddings, CohereEmbeddings, GeminiEmbeddings all normalize to RuntimeError).
EMBEDDING_ERRORS = (
    RuntimeError,  # local device failure or API backend normalization
    OSError,  # model files missing or corrupted (local backends)
    MemoryError,  # document too large for available RAM
    OSError,  # model files missing or corrupted (local backends)
    MemoryError,  # document too large for available RAM
)


class PipelineMessages:
    RATE_LIMIT = "LLM rate limit exceeded. Will retry on next sync."
    LLM_TIMEOUT = "LLM request timed out. Will retry on next sync."
    LLM_UNAVAILABLE = "LLM service temporarily unavailable. Will retry on next sync."
    LLM_BAD_GATEWAY = "LLM gateway error. Will retry on next sync."
    LLM_SERVER_ERROR = "LLM internal server error. Will retry on next sync."
    LLM_CONNECTION = "Could not reach the LLM service. Check network connectivity."
    RATE_LIMIT = "LLM rate limit exceeded. Will retry on next sync."
    LLM_TIMEOUT = "LLM request timed out. Will retry on next sync."
    LLM_UNAVAILABLE = "LLM service temporarily unavailable. Will retry on next sync."
    LLM_BAD_GATEWAY = "LLM gateway error. Will retry on next sync."
    LLM_SERVER_ERROR = "LLM internal server error. Will retry on next sync."
    LLM_CONNECTION = "Could not reach the LLM service. Check network connectivity."

    LLM_AUTH = "LLM authentication failed. Check your API key."
    LLM_PERMISSION = "LLM request denied. Check your account permissions."
    LLM_NOT_FOUND = "Model not found. Check your model configuration."
    LLM_BAD_REQUEST = "LLM rejected the request. Document content may be invalid."
    LLM_UNPROCESSABLE = (
        "Document exceeds the LLM context window even after optimization."
    )
    LLM_RESPONSE = "LLM returned an invalid response."
    LLM_AUTH = "LLM authentication failed. Check your API key."
    LLM_PERMISSION = "LLM request denied. Check your account permissions."
    LLM_NOT_FOUND = "Model not found. Check your model configuration."
    LLM_BAD_REQUEST = "LLM rejected the request. Document content may be invalid."
    LLM_UNPROCESSABLE = (
        "Document exceeds the LLM context window even after optimization."
    )
    LLM_RESPONSE = "LLM returned an invalid response."

    EMBEDDING_FAILED = (
        "Embedding failed. Check your embedding model configuration or service."
    )
    EMBEDDING_MODEL = "Embedding model files are missing or corrupted."
    EMBEDDING_MEMORY = "Not enough memory to embed this document."
    EMBEDDING_FAILED = (
        "Embedding failed. Check your embedding model configuration or service."
    )
    EMBEDDING_MODEL = "Embedding model files are missing or corrupted."
    EMBEDDING_MEMORY = "Not enough memory to embed this document."

    CHUNKING_OVERFLOW = "Document structure is too deeply nested to chunk."


def safe_exception_message(exc: Exception) -> str:
    try:
        return str(exc)
    except Exception:
        return "Something went wrong during indexing. Error details could not be retrieved."


def llm_retryable_message(exc: Exception) -> str:
    try:
        adapted = adapt_llm_exception(exc)
        if adapted.category is LLMErrorCategory.UNKNOWN:
            return safe_exception_message(exc)
        return adapted.user_message
    except Exception:
        return "Something went wrong when calling the LLM."


def llm_permanent_message(exc: Exception) -> str:
    try:
        adapted = adapt_llm_exception(exc)
        if adapted.category is LLMErrorCategory.UNKNOWN:
            return safe_exception_message(exc)
        return adapted.user_message
    except Exception:
        return "Something went wrong when calling the LLM."


def embedding_message(exc: Exception) -> str:
    try:
        if isinstance(exc, RuntimeError):
            return PipelineMessages.EMBEDDING_FAILED
        if isinstance(exc, OSError):
            return PipelineMessages.EMBEDDING_MODEL
        if isinstance(exc, MemoryError):
            return PipelineMessages.EMBEDDING_MEMORY
        return safe_exception_message(exc)
    except Exception:
        return "Something went wrong when generating the embedding."
