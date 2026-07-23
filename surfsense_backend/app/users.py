import logging
import uuid
from datetime import UTC, datetime

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.jwt import generate_jwt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.auth.session_cookies import access_expires_at, write_session
from app.config import config
from app.observability import analytics as ph_analytics
from app.db import (
    Prompt,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    async_session_maker,
    get_async_session,
    get_default_roles_config,
    get_user_db,
)
from app.prompts.system_defaults import SYSTEM_PROMPT_DEFAULTS
from app.utils.pat import PAT_PREFIX, maybe_touch_last_used, resolve_pat
from app.utils.refresh_tokens import create_refresh_token

logger = logging.getLogger(__name__)


SECRET = config.SECRET_KEY


if config.AUTH_TYPE == "GOOGLE":
    from httpx_oauth.clients.google import GoogleOAuth2

    google_oauth_client = GoogleOAuth2(
        config.GOOGLE_OAUTH_CLIENT_ID,
        config.GOOGLE_OAUTH_CLIENT_SECRET,
    )


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """
    Custom user manager extending fastapi-users BaseUserManager.

    Authentication returns a generic error for both non-existent accounts
    and incorrect passwords to comply with OWASP WSTG-IDNT-04 and
    prevent user enumeration attacks.
    """

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

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        try:
            async with async_session_maker() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(last_login=datetime.now(UTC))
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to update last_login for user {user.id}: {e}")

        # Authoritative login event (vs. the frontend's optimistic capture).
        ph_analytics.capture("auth_login_success", distinct_id=str(user.id))

    async def on_after_register(self, user: User, request: Request | None = None):
        """
        Called after a user registers. Creates a default workspace for the user
        so they can start chatting immediately without manual setup.
        """
        logger.info(f"User {user.id} has registered. Creating default workspace...")

        try:
            async with async_session_maker() as session:
                # Create default workspace
                default_workspace = Workspace(
                    name="My Workspace",
                    description="Your personal workspace",
                    user_id=user.id,
                )
                session.add(default_workspace)
                await session.flush()  # Get the workspace ID

                # Create default roles
                default_roles = get_default_roles_config()
                owner_role_id = None

                for role_config in default_roles:
                    db_role = WorkspaceRole(
                        name=role_config["name"],
                        description=role_config["description"],
                        permissions=role_config["permissions"],
                        is_default=role_config["is_default"],
                        is_system_role=role_config["is_system_role"],
                        workspace_id=default_workspace.id,
                    )
                    session.add(db_role)
                    await session.flush()

                    if role_config["name"] == "Owner":
                        owner_role_id = db_role.id

                # Create owner membership
                owner_membership = WorkspaceMembership(
                    user_id=user.id,
                    workspace_id=default_workspace.id,
                    role_id=owner_role_id,
                    is_owner=True,
                )
                session.add(owner_membership)

                for default in SYSTEM_PROMPT_DEFAULTS:
                    session.add(
                        Prompt(
                            user_id=user.id,
                            default_prompt_slug=default["slug"],
                            name=default["name"],
                            prompt=default["prompt"],
                            mode=default["mode"],
                            version=default["version"],
                        )
                    )

                await session.commit()
                logger.info(
                    f"Created default workspace (ID: {default_workspace.id}) for user {user.id}"
                )

                # Authoritative registration + auto-created default workspace.
                ph_analytics.capture(
                    "auth_registration_success", distinct_id=str(user.id)
                )
                ph_analytics.capture(
                    "workspace_created",
                    distinct_id=str(user.id),
                    properties={"client": "auto_register"},
                    groups={"workspace": str(default_workspace.id)},
                )
        except Exception as e:
            logger.error(f"Failed to create default workspace for user {user.id}: {e}")

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


class IatJWTStrategy(JWTStrategy[models.UP, models.ID]):
    async def write_token(self, user: models.UP) -> str:
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "iat": int(datetime.now(UTC).timestamp()),
        }
        return generate_jwt(
            data,
            self.encode_key,
            self.lifetime_seconds,
            algorithm=self.algorithm,
        )


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return IatJWTStrategy(
        secret=SECRET,
        lifetime_seconds=config.ACCESS_TOKEN_LIFETIME_SECONDS,
    )


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
        try:
            payload = jwt.decode(
                token, SECRET, algorithms=["HS256"], options={"verify_aud": False}
            )
            user_id = uuid.UUID(payload.get("sub"))
            refresh_token = await create_refresh_token(user_id)
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session",
            ) from e

        if config.AUTH_TYPE == "GOOGLE":
            response = RedirectResponse(
                f"{config.NEXT_FRONTEND_URL}/dashboard",
                status_code=302,
            )
        else:
            response = JSONResponse(
                {
                    "authenticated": True,
                    "access_expires_at": access_expires_at(token),
                }
            )

        write_session(response, token, refresh_token)
        return response


bearer_transport = CustomBearerTransport(tokenUrl="auth/jwt/login")


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])


def _token_meets_epoch(token: str) -> bool:
    min_issued_at = config.MIN_ISSUED_AT
    if min_issued_at <= 0:
        return True

    try:
        payload = jwt.decode(
            token, SECRET, algorithms=["HS256"], options={"verify_aud": False}
        )
    except jwt.PyJWTError:
        return False

    issued_at = payload.get("iat")
    return isinstance(issued_at, int | float) and int(issued_at) >= min_issued_at


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
) -> AuthContext:
    """Resolve the authenticated principal.

    Use this for authorization-sensitive routes where session-vs-PAT matters.
    FastAPI-Users still handles JWT mechanics; PATs are resolved here so RBAC
    receives the full SurfSense principal instead of a bare User.
    """
    def _stash(ctx: AuthContext) -> AuthContext:
        # Expose the resolved principal on request.state so downstream
        # middleware (e.g. PostHog pat_api_request attribution) can read it
        # without re-resolving auth.
        request.state.auth_context = ctx
        return ctx

    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, credential = auth_header.partition(" ")
        is_bearer = scheme.lower() == "bearer" and bool(credential)
        token = credential if is_bearer else auth_header.strip()

        if token.startswith(PAT_PREFIX):
            pat = await resolve_pat(session, token)
            if pat and pat.user and pat.user.is_active:
                maybe_touch_last_used(pat)
                return _stash(AuthContext.pat_auth(pat.user, pat))

        if is_bearer and _token_meets_epoch(token):
            try:
                user = await get_jwt_strategy().read_token(token, user_manager)
            except Exception:
                logger.exception("Failed to read bearer access token")
                user = None

            if user and user.is_active:
                return _stash(AuthContext.session(user))

    cookie_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if cookie_token and _token_meets_epoch(cookie_token):
        try:
            user = await get_jwt_strategy().read_token(cookie_token, user_manager)
        except Exception:
            logger.exception("Failed to read session cookie access token")
            user = None

        if user and user.is_active:
            return _stash(AuthContext.session(user))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )


async def allow_any_principal(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Allow either session or PAT principals for bootstrap probes only.

    Routes using this dependency intentionally have no workspace gate.
    Adding a new call site is a security decision and must be covered by
    the fail-closed PAT allowlist test.
    """
    return auth


async def require_session_context(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Require an interactive session and reject PAT-authenticated requests."""
    if not auth.is_session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an interactive session",
        )
    return auth
