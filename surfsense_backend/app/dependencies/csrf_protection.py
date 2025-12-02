"""
CSRF Protection Middleware and Dependencies
Provides defense-in-depth against CSRF attacks alongside SameSite cookies
"""
import secrets
from typing import Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class CSRFProtection:
    """
    CSRF Protection using Double Submit Cookie pattern
    
    How it works:
    1. Server generates a random CSRF token and sends it as both:
       - A cookie (csrf_token)
       - In the response body/header
    2. Client includes the token in request headers (X-CSRF-Token)
    3. Server validates that cookie value matches header value
    
    This prevents CSRF because attackers can read cookies but cannot
    set custom headers on cross-origin requests.
    """
    
    COOKIE_NAME = "csrf_token"
    HEADER_NAME = "X-CSRF-Token"
    
    # Methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    
    # Paths that don't require CSRF protection (login, public endpoints)
    EXEMPT_PATHS = {
        "/auth/jwt/login",
        "/auth/register", 
        "/auth/jwt/logout",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/docs",
        "/openapi.json",
        "/api/health",
    }
    
    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically secure CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_exempt(path: str) -> bool:
        """Check if path is exempt from CSRF protection"""
        return any(path.startswith(exempt) for exempt in CSRFProtection.EXEMPT_PATHS)
    
    @classmethod
    async def validate_csrf(cls, request: Request) -> None:
        """
        Validate CSRF token for state-changing requests
        
        Raises:
            HTTPException: If CSRF validation fails
        """
        # Skip validation for safe methods
        if request.method not in cls.PROTECTED_METHODS:
            return
        
        # Skip validation for exempt paths
        if cls.is_exempt(request.url.path):
            return
        
        # Get token from cookie
        cookie_token = request.cookies.get(cls.COOKIE_NAME)
        
        # Get token from header
        header_token = request.headers.get(cls.HEADER_NAME)
        
        # Both must be present
        if not cookie_token or not header_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing. Please refresh the page and try again."
            )
        
        # Tokens must match (constant-time comparison to prevent timing attacks)
        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed. Please refresh the page and try again."
            )
    
    @classmethod
    def set_csrf_cookie(cls, response: JSONResponse, token: Optional[str] = None) -> JSONResponse:
        """
        Set CSRF token cookie on response
        
        Args:
            response: FastAPI JSONResponse
            token: CSRF token (generates new one if not provided)
            
        Returns:
            Response with CSRF cookie set
        """
        if token is None:
            token = cls.generate_token()
        
        response.set_cookie(
            key=cls.COOKIE_NAME,
            value=token,
            httponly=False,  # Must be False so JavaScript can read it to send in headers
            secure=True,     # HTTPS only
            samesite="strict",  # CSRF protection
            max_age=3600,    # 1 hour
        )
        
        # Also include in response body for convenience
        if hasattr(response, 'body'):
            try:
                import json
                body = json.loads(response.body)
                body['csrf_token'] = token
                response.body = json.dumps(body).encode()
            except (json.JSONDecodeError, TypeError):
                pass  # If body is not JSON, skip
        
        return response


async def require_csrf_token(request: Request) -> None:
    """
    Dependency to require CSRF token validation
    
    Usage in routes:
        @router.post("/protected-endpoint")
        async def protected(csrf: None = Depends(require_csrf_token)):
            ...
    """
    await CSRFProtection.validate_csrf(request)
