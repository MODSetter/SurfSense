"""
Security Headers Middleware for SurfSense.

This middleware adds security headers to all HTTP responses to protect against
common web vulnerabilities like XSS, clickjacking, and MIME sniffing.

Headers Added:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- Content-Security-Policy: default-src 'self'
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), microphone=(), camera=()
"""

import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses.

    This middleware follows OWASP recommendations for secure headers configuration.
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        enable_csp: bool = True,
        csp_policy: str | None = None,
    ):
        """
        Initialize the security headers middleware.

        Args:
            app: The ASGI application
            enable_hsts: Whether to enable Strict-Transport-Security header
            enable_csp: Whether to enable Content-Security-Policy header
            csp_policy: Custom CSP policy (defaults to strict policy if not provided)
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp
        self.csp_policy = csp_policy or self._get_default_csp()

    def _build_csp_from_dict(self, csp_directives: dict[str, list[str]]) -> str:
        """
        Build a CSP string from a dictionary of directives.

        Args:
            csp_directives: Dictionary mapping directive names to lists of sources

        Returns:
            Formatted CSP policy string

        Example:
            {
                "default-src": ["'self'"],
                "script-src": ["'self'", "'unsafe-inline'"],
            }
            becomes:
            "default-src 'self'; script-src 'self' 'unsafe-inline'"
        """
        policy_parts = []
        for directive, sources in csp_directives.items():
            sources_str = " ".join(sources)
            policy_parts.append(f"{directive} {sources_str}")
        return "; ".join(policy_parts)

    def _get_default_csp(self) -> str:
        """
        Get default Content Security Policy.

        This is a strict policy that can be customized based on application needs.
        Uses a dictionary-based approach for better maintainability.
        """
        # For development, allow more sources; for production, be strict
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

        if is_production:
            # Strict production CSP
            csp_directives = {
                "default-src": ["'self'"],
                "script-src": ["'self'"],
                "style-src": ["'self'"],  # No unsafe-inline in production for better XSS protection
                "img-src": ["'self'", "data:", "https:"],
                "font-src": ["'self'"],
                "connect-src": ["'self'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"],
                "object-src": ["'none'"],  # Prevent Flash/plugins
                "upgrade-insecure-requests": [],  # Force HTTPS
            }
            # Note: If inline styles are needed, use nonce-based CSP:
            # Generate nonce per-request and add to style-src: ["'self'", "'nonce-{nonce}'"]
            # Then add nonce attribute to inline style tags: <style nonce="{nonce}">...</style>
        else:
            # More permissive for development
            csp_directives = {
                "default-src": ["'self'"],
                "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],  # Dev tools need eval
                "style-src": ["'self'", "'unsafe-inline'"],
                "img-src": ["'self'", "data:", "https:"],
                "font-src": ["'self'"],
                "connect-src": ["'self'", "http://localhost:*", "ws://localhost:*"],  # Dev server
                "frame-ancestors": ["'self'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"],
                "object-src": ["'none'"],
            }

        return self._build_csp_from_dict(csp_directives)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add security headers to the response.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        # X-Content-Type-Options: Prevent MIME sniffing
        # Prevents browsers from MIME-sniffing a response away from the declared content-type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options: Prevent clickjacking
        # Prevents the site from being framed, protecting against clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection: Enable XSS filter
        # Enables the browser's XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict-Transport-Security (HSTS): Force HTTPS
        # Only add in production and if enabled
        if self.enable_hsts:
            is_production = (
                os.getenv("ENVIRONMENT", "development").lower() == "production"
            )
            if is_production:
                # 1 year HSTS, including subdomains
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

        # Content-Security-Policy: Control resource loading
        # Prevents XSS and other injection attacks by controlling what resources can be loaded
        if self.enable_csp:
            response.headers["Content-Security-Policy"] = self.csp_policy

        # Referrer-Policy: Control referrer information
        # Controls how much referrer information is included with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Control browser features
        # Restricts access to browser features like geolocation, camera, microphone
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        # X-Permitted-Cross-Domain-Policies: Control Flash/PDF cross-domain
        # Prevents Adobe Flash and PDF from loading data cross-domain
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Cache-Control for sensitive endpoints
        # Prevent caching of sensitive data
        path = str(request.url.path)
        if any(
            path.startswith(sensitive_path)
            for sensitive_path in ["/auth/", "/api/", "/admin/", "/users/"]
        ):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"

        return response


def add_security_headers_middleware(app: ASGIApp, **kwargs) -> None:
    """
    Add security headers middleware to a FastAPI application.

    Args:
        app: The FastAPI application
        **kwargs: Additional configuration options for the middleware

    Example:
        ```python
        from fastapi import FastAPI
        from app.middleware.security_headers import add_security_headers_middleware

        app = FastAPI()
        add_security_headers_middleware(app)
        ```
    """
    app.add_middleware(SecurityHeadersMiddleware, **kwargs)
