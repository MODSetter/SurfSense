"""
CSRF Token Routes
Provides endpoints for CSRF token management
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.dependencies.csrf_protection import CSRFProtection

router = APIRouter(prefix="/api/v1/csrf", tags=["csrf"])


@router.get("/token")
async def get_csrf_token():
    """
    Get a CSRF token for the current session
    
    This endpoint generates and returns a CSRF token that must be included
    in all state-changing requests (POST, PUT, DELETE, PATCH).
    
    The token is set as both:
    - A cookie (for server-side validation)
    - In the response body (for client-side storage)
    
    Returns:
        JSONResponse with csrf_token in body and cookie
    """
    token = CSRFProtection.generate_token()
    
    response = JSONResponse({
        "csrf_token": token,
        "message": "CSRF token generated successfully"
    })
    
    # Set the CSRF cookie
    response.set_cookie(
        key=CSRFProtection.COOKIE_NAME,
        value=token,
        httponly=False,  # Must be False so JavaScript can read it
        secure=True,     # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=3600,    # 1 hour
    )
    
    return response
