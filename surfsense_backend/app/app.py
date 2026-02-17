import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from threading import Lock

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from limits.storage import MemoryStorage
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.agents.new_chat.checkpointer import (
    close_checkpointer,
    setup_checkpointer_tables,
)
from app.config import config, initialize_image_gen_router, initialize_llm_router
from app.db import User, create_db_and_tables, get_async_session
from app.routes import router as crud_router
from app.routes.auth_routes import router as auth_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.tasks.surfsense_docs_indexer import seed_surfsense_docs
from app.users import SECRET, auth_backend, current_active_user, fastapi_users

rate_limit_logger = logging.getLogger("surfsense.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# SlowAPI limiter — provides default rate limits (1024/min) for ALL routes
# via the ASGI middleware. This is the general safety net.
# in_memory_fallback ensures requests are still served (with per-worker
# in-memory limiting) when Redis is unreachable, instead of hanging.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=config.REDIS_APP_URL,
    default_limits=["1024/minute"],
    in_memory_fallback_enabled=True,
    in_memory_fallback=[MemoryStorage()],
)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom 429 handler that returns JSON matching our frontend error format."""
    retry_after = exc.detail.split("per")[-1].strip() if exc.detail else "60"
    return JSONResponse(
        status_code=429,
        content={"detail": "RATE_LIMIT_EXCEEDED"},
        headers={"Retry-After": retry_after},
    )


# ============================================================================
# Auth-Specific Rate Limits (Redis-backed with in-memory fallback)
# ============================================================================
# Stricter per-IP limits on auth endpoints to prevent:
# - Brute force password attacks
# - User enumeration via REGISTER_USER_ALREADY_EXISTS
# - Email spam via forgot-password
#
# Primary: Redis INCR+EXPIRE (shared across all workers).
# Fallback: In-memory sliding window (per-worker) when Redis is unavailable.
# Same Redis instance as SlowAPI / Celery.
_rate_limit_redis: redis.Redis | None = None

# In-memory fallback rate limiter (per-worker, used only when Redis is down)
_memory_rate_limits: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _get_rate_limit_redis() -> redis.Redis:
    """Get or create Redis client for auth rate limiting."""
    global _rate_limit_redis
    if _rate_limit_redis is None:
        _rate_limit_redis = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _rate_limit_redis


def _check_rate_limit_memory(
    client_ip: str, max_requests: int, window_seconds: int, scope: str
):
    """
    In-memory fallback rate limiter using a sliding window.
    Used only when Redis is unavailable. Per-worker only (not shared),
    so effective limit = max_requests x num_workers.
    """
    key = f"{scope}:{client_ip}"
    now = time.monotonic()

    with _memory_lock:
        # Evict timestamps outside the current window
        _memory_rate_limits[key] = [
            t for t in _memory_rate_limits[key] if now - t < window_seconds
        ]

        if len(_memory_rate_limits[key]) >= max_requests:
            rate_limit_logger.warning(
                f"Rate limit exceeded (in-memory fallback) on {scope} for IP {client_ip} "
                f"({len(_memory_rate_limits[key])}/{max_requests} in {window_seconds}s)"
            )
            raise HTTPException(
                status_code=429,
                detail="RATE_LIMIT_EXCEEDED",
            )

        _memory_rate_limits[key].append(now)


def _check_rate_limit(
    request: Request, max_requests: int, window_seconds: int, scope: str
):
    """
    Check per-IP rate limit using Redis. Raises 429 if exceeded.
    Uses atomic INCR + EXPIRE to avoid race conditions.
    Falls back to in-memory sliding window if Redis is unavailable.
    """
    client_ip = get_remote_address(request)
    key = f"surfsense:auth_rate_limit:{scope}:{client_ip}"

    try:
        r = _get_rate_limit_redis()

        # Atomic: increment first, then set TTL if this is a new key
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        result = pipe.execute()
    except (redis.exceptions.RedisError, OSError) as exc:
        # Redis unavailable — fall back to in-memory rate limiting
        rate_limit_logger.warning(
            f"Redis unavailable for rate limiting ({scope}), "
            f"falling back to in-memory limiter for {client_ip}: {exc}"
        )
        _check_rate_limit_memory(client_ip, max_requests, window_seconds, scope)
        return

    current_count = result[0]  # INCR returns the new value

    if current_count > max_requests:
        rate_limit_logger.warning(
            f"Rate limit exceeded on {scope} for IP {client_ip} "
            f"({current_count}/{max_requests} in {window_seconds}s)"
        )
        raise HTTPException(
            status_code=429,
            detail="RATE_LIMIT_EXCEEDED",
        )


def rate_limit_login(request: Request):
    """5 login attempts per minute per IP."""
    _check_rate_limit(request, max_requests=5, window_seconds=60, scope="login")


def rate_limit_register(request: Request):
    """3 registration attempts per minute per IP."""
    _check_rate_limit(request, max_requests=3, window_seconds=60, scope="register")


def rate_limit_password_reset(request: Request):
    """2 password reset attempts per minute per IP."""
    _check_rate_limit(
        request, max_requests=2, window_seconds=60, scope="password_reset"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()
    # Setup LangGraph checkpointer tables for conversation persistence
    await setup_checkpointer_tables()
    # Initialize LLM Router for Auto mode load balancing
    initialize_llm_router()
    # Initialize Image Generation Router for Auto mode load balancing
    initialize_image_gen_router()
    # Seed Surfsense documentation (with timeout so a slow embedding API
    # doesn't block startup indefinitely and make the container unresponsive)
    try:
        await asyncio.wait_for(seed_surfsense_docs(), timeout=120)
    except TimeoutError:
        logging.getLogger(__name__).warning(
            "Surfsense docs seeding timed out after 120s — skipping. "
            "Docs will be indexed on the next restart."
        )
    yield
    # Cleanup: close checkpointer connection on shutdown
    await close_checkpointer()


def registration_allowed():
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled"
        )
    return True


app = FastAPI(lifespan=lifespan)

# Register rate limiter and custom 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add SlowAPI middleware for automatic rate limiting
# Uses Starlette BaseHTTPMiddleware (not the raw ASGI variant) to avoid
# corrupting StreamingResponse — SlowAPIASGIMiddleware re-sends
# http.response.start on every body chunk, breaking SSE/streaming endpoints.
app.add_middleware(SlowAPIMiddleware)

# Add ProxyHeaders middleware FIRST to trust proxy headers (e.g., from Cloudflare)
# This ensures FastAPI uses HTTPS in redirects when behind a proxy
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Add CORS middleware
# When using credentials, we must specify exact origins (not "*")
# Build allowed origins list from NEXT_FRONTEND_URL
allowed_origins = []
if config.NEXT_FRONTEND_URL:
    allowed_origins.append(config.NEXT_FRONTEND_URL)
    # Also allow without trailing slash and with www/without www variants
    frontend_url = config.NEXT_FRONTEND_URL.rstrip("/")
    if frontend_url not in allowed_origins:
        allowed_origins.append(frontend_url)
    # Handle www variants
    if "://www." in frontend_url:
        non_www = frontend_url.replace("://www.", "://")
        if non_www not in allowed_origins:
            allowed_origins.append(non_www)
    elif "://" in frontend_url and "://www." not in frontend_url:
        # Add www variant
        www_url = frontend_url.replace("://", "://www.")
        if www_url not in allowed_origins:
            allowed_origins.append(www_url)

# For local development, also allow common localhost origins
if not config.BACKEND_URL or (
    config.NEXT_FRONTEND_URL and "localhost" in config.NEXT_FRONTEND_URL
):
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
    dependencies=[Depends(rate_limit_login)],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
    dependencies=[
        Depends(rate_limit_register),
        Depends(registration_allowed),  # blocks registration when disabled
    ],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(rate_limit_password_reset)],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Include custom auth routes (refresh token, logout)
app.include_router(auth_router)

if config.AUTH_TYPE == "GOOGLE":
    from fastapi.responses import RedirectResponse

    from app.users import google_oauth_client

    # Determine if we're in a secure context (HTTPS) or local development (HTTP)
    # The CSRF cookie must have secure=False for HTTP (localhost development)
    is_secure_context = config.BACKEND_URL and config.BACKEND_URL.startswith("https://")

    # For cross-origin OAuth (frontend and backend on different domains):
    # - SameSite=None is required to allow cross-origin cookie setting
    # - Secure=True is required when SameSite=None
    # For same-origin or local development, use SameSite=Lax (default)
    csrf_cookie_samesite = "none" if is_secure_context else "lax"

    # Extract the domain from BACKEND_URL for cookie domain setting
    # This helps with cross-site cookie issues in Firefox/Safari
    csrf_cookie_domain = None
    if config.BACKEND_URL:
        from urllib.parse import urlparse

        parsed_url = urlparse(config.BACKEND_URL)
        csrf_cookie_domain = parsed_url.hostname

    app.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client,
            auth_backend,
            SECRET,
            is_verified_by_default=True,
            csrf_token_cookie_secure=is_secure_context,
            csrf_token_cookie_samesite=csrf_cookie_samesite,
            csrf_token_cookie_httponly=False,  # Required for cross-site OAuth in Firefox/Safari
        )
        if not config.BACKEND_URL
        else fastapi_users.get_oauth_router(
            google_oauth_client,
            auth_backend,
            SECRET,
            is_verified_by_default=True,
            redirect_url=f"{config.BACKEND_URL}/auth/google/callback",
            csrf_token_cookie_secure=is_secure_context,
            csrf_token_cookie_samesite=csrf_cookie_samesite,
            csrf_token_cookie_httponly=False,  # Required for cross-site OAuth in Firefox/Safari
            csrf_token_cookie_domain=csrf_cookie_domain,  # Explicitly set cookie domain
        ),
        prefix="/auth/google",
        tags=["auth"],
        dependencies=[
            Depends(registration_allowed)
        ],  # blocks OAuth registration when disabled
    )

    # Add a redirect-based authorize endpoint for Firefox/Safari compatibility
    # This endpoint performs a server-side redirect instead of returning JSON
    # which fixes cross-site cookie issues where browsers don't send cookies
    # set via cross-origin fetch requests on subsequent redirects
    @app.get("/auth/google/authorize-redirect", tags=["auth"])
    async def google_authorize_redirect(
        request: Request,
    ):
        """
        Redirect-based OAuth authorization endpoint.

        Unlike the standard /auth/google/authorize endpoint that returns JSON,
        this endpoint directly redirects the browser to Google's OAuth page.
        This fixes CSRF cookie issues in Firefox and Safari where cookies set
        via cross-origin fetch requests are not sent on subsequent redirects.
        """
        import secrets

        from fastapi_users.router.oauth import generate_state_token

        # Generate CSRF token
        csrf_token = secrets.token_urlsafe(32)

        # Build state token
        state_data = {"csrftoken": csrf_token}
        state = generate_state_token(state_data, SECRET, lifetime_seconds=3600)

        # Get the callback URL
        if config.BACKEND_URL:
            redirect_url = f"{config.BACKEND_URL}/auth/google/callback"
        else:
            redirect_url = str(request.url_for("oauth:google.jwt.callback"))

        # Get authorization URL from Google
        authorization_url = await google_oauth_client.get_authorization_url(
            redirect_url,
            state,
            scope=["openid", "email", "profile"],
        )

        # Create redirect response and set CSRF cookie
        response = RedirectResponse(url=authorization_url, status_code=302)
        response.set_cookie(
            key="fastapiusersoauthcsrf",
            value=csrf_token,
            max_age=3600,
            path="/",
            domain=csrf_cookie_domain,
            secure=is_secure_context,
            httponly=False,  # Required for cross-site OAuth in Firefox/Safari
            samesite=csrf_cookie_samesite,
        )

        return response


app.include_router(crud_router, prefix="/api/v1", tags=["crud"])


@app.get("/health", tags=["health"])
@limiter.exempt
async def health_check():
    """Lightweight liveness probe exempt from rate limiting."""
    return {"status": "ok"}


@app.get("/verify-token")
async def authenticated_route(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return {"message": "Token is valid"}
