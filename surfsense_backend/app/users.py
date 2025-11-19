import uuid

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel

from app.config import config
from app.db import User, get_user_db


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
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        # SECURITY: Do not log the actual reset token
        # In production, send the token via email to the user
        print(f"Password reset requested for user {user.id}. Token generated.")
        # TODO: Implement email sending with the reset token

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        # SECURITY: Do not log the actual verification token
        # In production, send the token via email to the user
        print(f"Email verification requested for user {user.id}. Token generated.")
        # TODO: Implement email sending with the verification token


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    # SECURITY: Reduced from 24 hours to 1 hour to limit exposure window
    # Consider implementing refresh tokens for better security
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


# # COOKIE AUTH | Uncomment if you want to use cookie auth.
# from fastapi_users.authentication import (
#     CookieTransport,
# )
# class CustomCookieTransport(CookieTransport):
#     async def get_login_response(self, token: str) -> Response:
#         response = RedirectResponse(config.OAUTH_REDIRECT_URL, status_code=302)
#         return self._set_login_cookie(response, token)

# cookie_transport = CustomCookieTransport(
#     cookie_max_age=3600,
# )

# auth_backend = AuthenticationBackend(
#     name="jwt",
#     transport=cookie_transport,
#     get_strategy=get_jwt_strategy,
# )


# BEARER AUTH CODE.
# SECURITY WARNING: Passing JWT tokens in URL query parameters is not recommended
# as they can be exposed in browser history, server logs, and referrer headers.
# Consider using:
# 1. HTTP-only cookies (see commented CookieTransport above)
# 2. A short-lived authorization code that can be exchanged for a token
# 3. POST-based token exchange with the frontend
class CustomBearerTransport(BearerTransport):
    async def get_login_response(self, token: str) -> Response:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
        # TODO: Replace URL parameter with a more secure token exchange mechanism
        redirect_url = f"{config.NEXT_FRONTEND_URL}/auth/callback?token={bearer_response.access_token}"
        if config.AUTH_TYPE == "GOOGLE":
            return RedirectResponse(redirect_url, status_code=302)
        else:
            return JSONResponse(bearer_response.model_dump())


bearer_transport = CustomBearerTransport(tokenUrl="auth/jwt/login")


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
