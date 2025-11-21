"""
FastAPI dependencies for the SurfSense application.

This package contains reusable dependency functions for various
cross-cutting concerns like rate limiting, authentication, etc.
"""

from app.dependencies.rate_limit import check_rate_limit

__all__ = ["check_rate_limit"]
