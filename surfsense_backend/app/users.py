import logging
import uuid

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel

from app.config import config
from app.db import User, get_user_db

logger = logging.getLogger(__name__)


class BearerResponse(BaseModel):
    access_token: str
    token_type: str


SECRET = config.SECRET_KEY

if config.AUTH_TYPE == "GOOGLE":
    from httpx_oauth.clients.google import GoogleOAuth2

    google_oauth_client = GoogleOAuth2(
        config.GOOGLE_OAUTH_CLIENT_ID,
        config.GOOGLE_OAUTH_CLIENT_SECRET,
    )


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Request | None = None):
        # Log user registration without exposing sensitive data
        logger.info("User %s has registered.", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        # SECURITY: Do not log the actual reset token
        # In production, send the token via email to the user
        logger.info("Password reset requested for user %s. Token generated.", user.id)
        # TODO: Implement email sending with the reset token

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        # SECURITY: Do not log the actual verification token
        # In production, send the token via email to the user
        logger.info("Email verification requested for user %s. Token generated.", user.id)
        # TODO: Implement email sending with the verification token


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    # SECURITY: Token lifetime set to 1 hour for better security
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


# SECURE COOKIE AUTH - HttpOnly cookies prevent XSS attacks
class CustomCookieTransport(CookieTransport):
    async def get_login_response(self, token: str) -> Response:
        if config.AUTH_TYPE == "GOOGLE":
            # For OAuth, redirect to frontend callback
            response = RedirectResponse(config.OAUTH_REDIRECT_URL, status_code=302)
        else:
            # For regular login, return JSON success
            response = JSONResponse({"success": True, "message": "Login successful"})
        return self._set_login_cookie(response, token)
    
    async def get_logout_response(self) -> Response:
        response = JSONResponse({"success": True, "message": "Logout successful"})
        return self._set_logout_cookie(response)


cookie_transport = CustomCookieTransport(
    cookie_max_age=3600,  # 1 hour
    cookie_name="surfsense_auth",
    cookie_httponly=True,  # SECURITY: Prevents JavaScript access (XSS protection)
    cookie_secure=True,     # SECURITY: Only send over HTTPS
    cookie_samesite="lax",  # SECURITY: CSRF protection
)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)


# LEGACY BEARER AUTH - Keeping for backward compatibility during transition
# TODO: Remove after all clients migrate to cookie auth
class CustomBearerTransport(BearerTransport):
    async def get_login_response(self, token: str) -> Response:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
        redirect_url = f"{config.NEXT_FRONTEND_URL}/auth/callback#token={bearer_response.access_token}"
        if config.AUTH_TYPE == "GOOGLE":
            return RedirectResponse(redirect_url, status_code=302)
        else:
            return JSONResponse(bearer_response.model_dump())


bearer_transport = CustomBearerTransport(tokenUrl="auth/jwt/login")

# Bearer backend for backward compatibility (to be deprecated)
bearer_auth_backend = AuthenticationBackend(
    name="jwt-bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Support both cookie and bearer auth during transition
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, 
    [auth_backend, bearer_auth_backend]  # Cookie auth is primary, bearer for backward compatibility
)

current_active_user = fastapi_users.current_user(active=True)
