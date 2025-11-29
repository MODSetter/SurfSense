"""
Centralized rate limiter configuration.

This module provides a shared rate limiter instance and Redis configuration
to avoid code duplication across route files.
"""

from __future__ import annotations

import os

from slowapi import Limiter

from app.dependencies.rate_limit import secure_rate_limit_key

# Get Redis URL for rate limiter shared storage
# Uses same Redis instance as Celery for rate limit counters
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Shared rate limiter instance with Redis storage backend
# Uses secure_rate_limit_key which validates proxy headers against trusted proxies
# This prevents IP spoofing attacks via forged X-Forwarded-For headers
# storage_uri ensures all Limiter instances share the same rate limit counters
limiter = Limiter(key_func=secure_rate_limit_key, storage_uri=REDIS_URL)
