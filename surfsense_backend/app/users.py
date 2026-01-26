import logging
import uuid

import httpx
from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from pydantic import BaseModel

from app.config import config
from app.db import (
    SearchSpace,
    SearchSpaceMembership,
    SearchSpaceRole,
    User,
    async_session_maker,
    get_default_roles_config,
    get_user_db,
)

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

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
        request: Request | None = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> User:
        """
        Override OAuth callback to capture Google profile data (name, avatar).
        """
        # Call parent implementation to create/get user
        user = await super().oauth_callback(
            oauth_name,
            access_token,
            account_id,
            account_email,
            expires_at,
            refresh_token,
            request,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
        )

        # Fetch and store Google profile data if not already set
        if oauth_name == "google" and (not user.display_name or not user.avatar_url):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://people.googleapis.com/v1/people/me",
                        params={"personFields": "names,photos"},
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    response.raise_for_status()
                    profile = response.json()

                update_dict = {}

                # Extract name from names array
                names = profile.get("names", [])
                if not user.display_name and names:
                    display_name = names[0].get("displayName")
                    if display_name:
                        update_dict["display_name"] = display_name

                # Extract photo URL from photos array
                photos = profile.get("photos", [])
                if not user.avatar_url and photos:
                    photo_url = photos[0].get("url")
                    if photo_url:
                        update_dict["avatar_url"] = photo_url

                if update_dict:
                    user = await self.user_db.update(user, update_dict)

            except Exception as e:
                logger.warning(f"Failed to fetch Google profile: {e}")

        return user

    async def on_after_register(self, user: User, request: Request | None = None):
        """
        Called after a user registers. Creates a default search space for the user
        so they can start chatting immediately without manual setup.
        """
        logger.info(f"User {user.id} has registered. Creating default search space...")

        try:
            async with async_session_maker() as session:
                # Create default search space
                default_search_space = SearchSpace(
                    name="My Search Space",
                    description="Your personal search space",
                    user_id=user.id,
                )
                session.add(default_search_space)
                await session.flush()  # Get the search space ID

                # Create default roles
                default_roles = get_default_roles_config()
                owner_role_id = None

                for role_config in default_roles:
                    db_role = SearchSpaceRole(
                        name=role_config["name"],
                        description=role_config["description"],
                        permissions=role_config["permissions"],
                        is_default=role_config["is_default"],
                        is_system_role=role_config["is_system_role"],
                        search_space_id=default_search_space.id,
                    )
                    session.add(db_role)
                    await session.flush()

                    if role_config["name"] == "Owner":
                        owner_role_id = db_role.id

                # Create owner membership
                owner_membership = SearchSpaceMembership(
                    user_id=user.id,
                    search_space_id=default_search_space.id,
                    role_id=owner_role_id,
                    is_owner=True,
                )
                session.add(owner_membership)

                await session.commit()
                logger.info(
                    f"Created default search space (ID: {default_search_space.id}) for user {user.id}"
                )
        except Exception as e:
            logger.error(
                f"Failed to create default search space for user {user.id}: {e}"
            )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24)


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
class CustomBearerTransport(BearerTransport):
    async def get_login_response(self, token: str) -> Response:
        bearer_response = BearerResponse(access_token=token, token_type="bearer")
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
current_optional_user = fastapi_users.current_user(active=True, optional=True)
