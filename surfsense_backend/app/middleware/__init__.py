"""
Middleware package for SurfSense backend.

This package contains custom middleware components for the application.
"""

from app.middleware.security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
