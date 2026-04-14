import logging
import secrets
import unicodedata
from datetime import UTC, datetime

from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelper  # singleton below
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import config
from app.db import User, async_session_maker

logger = logging.getLogger(__name__)
_password_helper = PasswordHelper()

_DEFAULT_BYPASS_PATHS = ["/health"]
_LAST_LOGIN_THROTTLE_SECONDS = 300


def _normalise_email(email: str) -> str:
    # NFKC normalisation collapses Unicode lookalikes before lowercasing,
    # preventing homoglyph spoofing (e.g. fullwidth latin chars).
    return unicodedata.normalize("NFKC", email).strip().lower()


def _coerce_bypass_paths(setting) -> list[str]:
    if not setting:
        return list(_DEFAULT_BYPASS_PATHS)
    if isinstance(setting, str):
        return [p.strip() for p in setting.split(",") if p.strip()]
    return list(setting)


def _is_bypass_path(path: str, bypass_paths: list[str]) -> bool:
    # Match exact path OR a true subpath (e.g. /health/ready) but NOT a path that
    # merely starts with the same characters (e.g. /healthz must NOT bypass /health).
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in bypass_paths)


class ProxyAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware for mPass proxy authentication.

    oauth2-proxy sets X-Auth-Request-Email on every request that has passed
    OIDC validation. This middleware reads that header, finds or creates the
    corresponding SurfSense user, and injects them into request.state.proxy_user
    so the current_active_user dependency sees a fully authenticated user
    without requiring a JWT token.

    Security / trust model
    ----------------------
    This middleware trusts X-Auth-Request-Email unconditionally. That is safe
    because:
      1. Traefik ForwardAuth overwrites X-Auth-Request-* headers on every
         request, so they cannot be spoofed by a browser or external client.
      2. In production the app container does not expose its port externally —
         only Traefik is public-facing, so there is no direct path to the app
         that bypasses header rewriting.

    A shared-secret header (set by oauth2-proxy, forwarded via Traefik
    authResponseHeaders, checked here) would add defense-in-depth against a
    misconfigured ingress but is not required given the network topology above.
    Add it if the threat model ever changes (e.g. the app port becomes reachable
    inside a zero-trust network where internal callers could forge headers).
    """

    def __init__(self, app):
        super().__init__(app)
        self.bypass_paths = _coerce_bypass_paths(
            getattr(config, "MPASS_BYPASS_PATHS", None)
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Already injected on this request cycle (idempotent)
        if getattr(request.state, "proxy_user", None) is not None:
            return await call_next(request)

        if _is_bypass_path(request.url.path, self.bypass_paths):
            return await call_next(request)

        raw_email = request.headers.get("x-auth-request-email")
        if not raw_email:
            logger.debug(
                "ProxyAuth: x-auth-request-email missing on %s", request.url.path
            )
            return await call_next(request)

        user = await self._resolve_user(_normalise_email(raw_email), request)

        # Respect deactivated accounts — mPass authentication does not
        # override an explicit SurfSense account suspension.
        if user is None or not user.is_active:
            logger.warning("ProxyAuth: user inactive or not found for %r", raw_email)
            return await call_next(request)

        logger.debug("ProxyAuth: injected user id=%s for %r", user.id, user.email)
        request.state.proxy_user = user
        return await call_next(request)

    async def _resolve_user(self, email: str, request: Request) -> User | None:
        try:
            async with async_session_maker() as session:
                result = await session.execute(select(User).where(User.email == email))
                user = result.unique().scalar_one_or_none()
                created = False

                if user is None:
                    hashed_password = _password_helper.hash(secrets.token_urlsafe(32))
                    user = User(
                        email=email,
                        hashed_password=hashed_password,
                        is_active=True,
                        is_verified=True,
                        is_superuser=False,
                    )
                    session.add(user)
                    try:
                        await session.commit()
                        await session.refresh(user)
                        created = True
                    except IntegrityError as exc:
                        # Concurrent request raced us to the insert — fall back
                        # to SELECT by email and re-raise if still not found.
                        await session.rollback()
                        result = await session.execute(
                            select(User).where(User.email == email)
                        )
                        user = result.unique().scalar_one_or_none()
                        if user is None:
                            logger.error(
                                "ProxyAuth: IntegrityError but user still not found "
                                "for %s: %s",
                                email,
                                exc,
                            )
                            return None

                # Update last_login at most once every 5 minutes per user.
                # Unlike Plane (Django session — one DB write per login session),
                # FastAPI has no server-side session so this middleware runs on
                # every request. Writing last_login unconditionally would add an
                # UPDATE + COMMIT to every API call; throttling keeps it cheap.
                now = datetime.now(UTC)
                needs_update = created or (
                    user.last_login is None
                    or (now - user.last_login).total_seconds()
                    > _LAST_LOGIN_THROTTLE_SECONDS
                )
                if needs_update:
                    try:
                        await session.execute(
                            update(User)
                            .where(User.id == user.id)
                            .values(last_login=now)
                        )
                        await session.commit()
                    except Exception:
                        logger.warning(
                            "ProxyAuth: failed to update last_login for %s", email
                        )

                if created:
                    # Trigger on_after_register so the default SearchSpace,
                    # RBAC roles and system prompts are created — same as
                    # Google OAuth and email/password signup.
                    # Use a fresh session so UserManager always has a clean connection.
                    # Re-fetch user in reg_session to avoid DetachedInstanceError —
                    # the user object from the outer session (or a rolled-back session
                    # after an IntegrityError race) must not be used across sessions.
                    try:
                        from app.users import UserManager

                        async with async_session_maker() as reg_session:
                            reg_result = await reg_session.execute(
                                select(User).where(User.id == user.id)
                            )
                            reg_user = reg_result.unique().scalar_one_or_none()
                            if reg_user is None:
                                raise RuntimeError(
                                    f"ProxyAuth: user {user.id} vanished before on_after_register"
                                )

                            user_db = SQLAlchemyUserDatabase(reg_session, User)
                            user_manager = UserManager(user_db)
                            await user_manager.on_after_register(
                                reg_user, request=request
                            )
                    except Exception:
                        logger.exception(
                            "ProxyAuth: on_after_register failed for %s — "
                            "user created but default search space may be missing",
                            email,
                        )

                return user

        except Exception:
            logger.exception("ProxyAuth: unexpected error resolving user for %s", email)
            return None
