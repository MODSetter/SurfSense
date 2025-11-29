"""
Structured logging configuration for SurfSense.

This module configures structlog for JSON-formatted logging with contextual
information, making logs easier to parse and analyze in production environments.
"""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.

    Sets up structlog with JSON output, timestamps, log levels, and contextual
    information. Logs are written to stdout for easy capture by log aggregation
    tools (e.g., CloudWatch, Datadog, ELK stack).

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> from app.utils.logger import configure_logging
        >>> configure_logging("INFO")
        >>> logger = get_logger(__name__)
        >>> logger.info("user_action", user_id=123, action="login")
        {"event": "user_action", "user_id": 123, "action": "login", ...}
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Configure structlog processors
    structlog.configure(
        processors=[
            # Add context variables (set with structlog.contextvars.bind_contextvars)
            structlog.contextvars.merge_contextvars,
            # Add log level to log entries
            structlog.stdlib.add_log_level,
            # Add logger name to log entries
            structlog.stdlib.add_logger_name,
            # Filter by log level
            structlog.stdlib.filter_by_level,
            # Format positional arguments into the event message
            structlog.stdlib.PositionalArgumentsFormatter(),
            # Add ISO 8601 timestamp
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Add stack info for errors
            structlog.processors.StackInfoRenderer(),
            # Format exception info nicely
            structlog.processors.format_exc_info,
            # Ensure strings are unicode
            structlog.processors.UnicodeDecoder(),
            # Render as JSON for easy parsing
            structlog.processors.JSONRenderer(),
        ],
        # Use stdlib logging as the final output
        wrapper_class=structlog.stdlib.BoundLogger,
        # Context class for storing contextual information
        context_class=dict,
        # Logger factory - integrates with stdlib logging
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache loggers for performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("request_processed", path="/api/v1/documents", status=200)
        >>> logger.error("database_error", error="Connection timeout", retry_count=3)
    """
    return structlog.get_logger(name)


# Convenience function for adding request context
def bind_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Bind request context to all subsequent log entries.

    This adds contextual information to all logs within the current async context,
    making it easier to trace requests through the system.

    Args:
        request_id: Unique request ID (e.g., from X-Request-ID header)
        user_id: Authenticated user ID
        ip_address: Client IP address

    Example:
        >>> bind_request_context(request_id="abc123", user_id="user_456")
        >>> logger.info("processing_request")  # Will include request_id and user_id
    """
    context = {}
    if request_id:
        context["request_id"] = request_id
    if user_id:
        context["user_id"] = user_id
    if ip_address:
        context["ip_address"] = ip_address

    if context:
        structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """
    Clear request context from the current async context.

    Call this at the end of request processing to avoid leaking context
    to subsequent requests.

    Example:
        >>> bind_request_context(request_id="abc123")
        >>> logger.info("request_start")
        >>> # ... process request ...
        >>> clear_request_context()
    """
    structlog.contextvars.clear_contextvars()
