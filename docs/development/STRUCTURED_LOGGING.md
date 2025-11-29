# Structured Logging in SurfSense

## Overview

SurfSense uses [structlog](https://www.structlog.org/) for structured logging with JSON output. This makes logs machine-readable and easier to parse, search, and analyze in production environments.

## Why Structured Logging?

- **Machine-readable**: JSON format is easily parsed by log aggregation tools
- **Contextual**: Attach structured data to log entries (user IDs, request IDs, etc.)
- **Searchable**: Filter logs by specific fields instead of regex on strings
- **Consistent**: Standardized format across all services
- **Production-ready**: Integrates with CloudWatch, Datadog, ELK, Splunk, etc.

## Configuration

Structured logging is configured automatically at application startup in `app/app.py`:

```python
from app.utils.logger import configure_logging, get_logger

# Configure at startup (reads LOG_LEVEL from environment)
configure_logging()

# Get a logger instance
logger = get_logger(__name__)
```

### Environment Variables

- `LOG_LEVEL`: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: `INFO`

```bash
export LOG_LEVEL=DEBUG
```

## Usage Examples

### Basic Logging

```python
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Simple log message
logger.info("user_registered")

# Log with structured data
logger.info("user_login", user_id=123, email="user@example.com")

# Error logging
logger.error("database_error", error="Connection timeout", retry_count=3)
```

### Output Format

Logs are output as JSON:

```json
{
  "event": "user_login",
  "user_id": 123,
  "email": "user@example.com",
  "timestamp": "2025-11-29T10:30:00.123456Z",
  "level": "info",
  "logger": "app.routes.auth"
}
```

### Request Context

Add context to all logs within a request:

```python
from app.utils.logger import bind_request_context, clear_request_context, get_logger

logger = get_logger(__name__)

async def process_request(request_id: str, user_id: str):
    # Bind context at request start
    bind_request_context(
        request_id=request_id,
        user_id=user_id,
        ip_address="192.168.1.1"
    )

    # All subsequent logs include context
    logger.info("processing_upload")  # Includes request_id, user_id, ip_address
    logger.info("upload_complete", file_count=5)

    # Clear context at request end
    clear_request_context()
```

### Exception Logging

Automatically includes stack traces:

```python
try:
    result = dangerous_operation()
except Exception as e:
    logger.error(
        "operation_failed",
        operation="dangerous_operation",
        error_type=type(e).__name__,
        exc_info=True  # Include full stack trace
    )
```

## Log Levels

Use appropriate log levels:

- **DEBUG**: Detailed diagnostic information (dev only)
- **INFO**: General informational messages
- **WARNING**: Warning messages for recoverable issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

```python
logger.debug("cache_lookup", key="user:123", found=True)
logger.info("request_processed", path="/api/documents", duration_ms=45)
logger.warning("rate_limit_approaching", user_id=123, requests=95, limit=100)
logger.error("api_call_failed", service="github", status=500)
logger.critical("database_unreachable", attempts=5)
```

## Best Practices

### ✅ DO

```python
# Use structured fields instead of string interpolation
logger.info("user_action", user_id=123, action="login", success=True)

# Use snake_case for event names
logger.info("password_reset_requested", user_id=456)

# Include relevant context
logger.error("payment_failed", user_id=789, amount=99.99, currency="USD", error="Card declined")
```

### ❌ DON'T

```python
# Don't use string interpolation (not structured)
logger.info(f"User {user_id} performed action {action}")

# Don't use camelCase for events
logger.info("userActionCompleted")

# Don't log sensitive data
logger.info("login_attempt", password="secret123")  # NEVER!
```

## Sensitive Data

**NEVER** log:
- Passwords
- API keys or tokens
- Credit card numbers
- Social security numbers
- Personal health information

Instead, log identifiers or hashed values:

```python
# ❌ Bad
logger.info("api_request", api_key="sk_live_abc123")

# ✅ Good
logger.info("api_request", api_key_prefix="sk_live_abc...", user_id=123)
```

## Production Integration

### CloudWatch Logs

JSON logs are automatically parsed by CloudWatch Logs Insights:

```sql
fields @timestamp, event, user_id, error
| filter level = "error"
| sort @timestamp desc
| limit 100
```

### Datadog

Configure JSON parsing in Datadog agent:

```yaml
logs:
  - type: file
    path: /var/log/surfsense/*.log
    service: surfsense-backend
    source: python
    sourcecategory: application
```

### ELK Stack

Logstash JSON codec automatically parses structured logs:

```ruby
input {
  file {
    path => "/var/log/surfsense/*.log"
    codec => json
  }
}
```

## Common Event Names

Standardized event names used throughout SurfSense:

| Event | Description |
|-------|-------------|
| `user_login` | User authentication |
| `user_logout` | User logout |
| `token_verified` | JWT token verification |
| `file_uploaded` | File upload |
| `document_created` | Document creation |
| `api_request` | External API call |
| `database_query` | Database operation |
| `rate_limit_exceeded` | Rate limit hit |
| `validation_error` | Input validation failure |

## Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
uvicorn app.app:app --reload
```

### Filter Specific Loggers

```python
# In app/utils/logger.py, modify configure_logging():
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # Quiet SQL logs
logging.getLogger("app.services").setLevel(logging.DEBUG)  # Verbose service logs
```

### Pretty Print for Development

For local development, you can temporarily use a pretty printer:

```python
# In app/utils/logger.py, replace JSONRenderer with:
structlog.dev.ConsoleRenderer()  # Human-readable colored output
```

## Performance

Structured logging adds minimal overhead:
- Lazy evaluation of log messages
- Logger caching for performance
- Async-safe context management
- No blocking I/O (writes to stdout)

## Migration Guide

Converting old logging to structured logging:

### Before (string formatting)

```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"User {user_id} uploaded {file_count} files")
```

### After (structured)

```python
from app.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("files_uploaded", user_id=user_id, file_count=file_count)
```

## Testing

Test logs in unit tests:

```python
import pytest
import structlog

def test_user_login(caplog):
    from app.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("user_login", user_id=123)

    # Check log was emitted
    assert "user_login" in caplog.text
```

## Resources

- [structlog Documentation](https://www.structlog.org/)
- [Best Practices for Logging](https://12factor.net/logs)
- [JSON Logging Tutorial](https://www.structlog.org/en/stable/getting-started.html)

## Support

For questions about logging:
1. Check existing logs in `app/` for examples
2. Review `app/utils/logger.py` for configuration
3. Consult structlog documentation
4. Create a GitHub issue if needed
