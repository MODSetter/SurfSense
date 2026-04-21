import asyncio
import gc
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from threading import Lock

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address  # noqa: F401 — kept for reference
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.agents.new_chat.checkpointer import (
    close_checkpointer,
    setup_checkpointer_tables,
)
from app.config import (
    config,
    initialize_image_gen_router,
    initialize_llm_router,
    initialize_openrouter_integration,
    initialize_vision_llm_router,
)
from app.db import User, create_db_and_tables, get_async_session
from app.exceptions import GENERIC_5XX_MESSAGE, ISSUES_URL, SurfSenseError
from app.rate_limiter import get_real_client_ip, limiter
from app.routes import router as crud_router
from app.routes.auth_routes import router as auth_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.tasks.surfsense_docs_indexer import seed_surfsense_docs
from app.users import SECRET, auth_backend, current_active_user, fastapi_users
from app.utils.perf import get_perf_logger, log_system_snapshot

_error_logger = logging.getLogger("surfsense.errors")

rate_limit_logger = logging.getLogger("surfsense.rate_limit")


# ============================================================================
# Rate Limiting Configuration (SlowAPI + Redis)
# ============================================================================
# Uses the same Redis instance as Celery for zero additional infrastructure.
# Protects auth endpoints from brute force and user enumeration attacks.

# limiter is imported from app.rate_limiter (shared module to avoid circular imports)


def _get_request_id(request: Request) -> str:
    """Return the request ID from state, header, or generate a new one."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    return request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")


def _build_error_response(
    status_code: int,
    message: str,
    *,
    code: str = "INTERNAL_ERROR",
    request_id: str = "",
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standardized error envelope (new ``error`` + legacy ``detail``)."""
    body = {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "report_url": ISSUES_URL,
        },
        "detail": message,
    }
    headers = {"X-Request-ID": request_id}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


def _surfsense_error_handler(request: Request, exc: SurfSenseError) -> JSONResponse:
    """Handle our own structured exceptions."""
    rid = _get_request_id(request)
    if exc.status_code >= 500:
        _error_logger.error(
            "[%s] %s - %s: %s",
            rid,
            request.url.path,
            exc.code,
            exc,
            exc_info=True,
        )
    message = exc.message if exc.safe_for_client else GENERIC_5XX_MESSAGE
    return _build_error_response(
        exc.status_code, message, code=exc.code, request_id=rid
    )


def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap FastAPI/Starlette HTTPExceptions into the standard envelope."""
    rid = _get_request_id(request)

    # Structured dict details (e.g. {"code": "CAPTCHA_REQUIRED", "message": "..."})
    # are preserved so the frontend can parse them.
    if isinstance(exc.detail, dict):
        err_code = exc.detail.get("code", _status_to_code(exc.status_code))
        message = exc.detail.get("message", str(exc.detail))
        if exc.status_code >= 500:
            _error_logger.error(
                "[%s] %s - HTTPException %d: %s",
                rid,
                request.url.path,
                exc.status_code,
                message,
            )
            if exc.status_code == 500:
                message = GENERIC_5XX_MESSAGE
                err_code = "INTERNAL_ERROR"
        body = {
            "error": {
                "code": err_code,
                "message": message,
                "status": exc.status_code,
                "request_id": rid,
                "timestamp": datetime.now(UTC).isoformat(),
                "report_url": ISSUES_URL,
            },
            "detail": exc.detail,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers={"X-Request-ID": rid},
        )

    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if exc.status_code >= 500:
        _error_logger.error(
            "[%s] %s - HTTPException %d: %s",
            rid,
            request.url.path,
            exc.status_code,
            detail,
        )
        if exc.status_code == 500:
            detail = GENERIC_5XX_MESSAGE
    code = _status_to_code(exc.status_code, detail)
    return _build_error_response(exc.status_code, detail, code=code, request_id=rid)


def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 with field-level detail in the standard envelope."""
    rid = _get_request_id(request)
    fields = []
    for err in exc.errors():
        loc = " -> ".join(str(part) for part in err.get("loc", []))
        fields.append(f"{loc}: {err.get('msg', 'invalid')}")
    message = (
        f"Validation failed: {'; '.join(fields)}" if fields else "Validation failed."
    )
    return _build_error_response(422, message, code="VALIDATION_ERROR", request_id=rid)


def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log full traceback, return sanitized 500."""
    rid = _get_request_id(request)
    _error_logger.error(
        "[%s] Unhandled exception on %s %s",
        rid,
        request.method,
        request.url.path,
        exc_info=True,
    )
    return _build_error_response(
        500, GENERIC_5XX_MESSAGE, code="INTERNAL_ERROR", request_id=rid
    )


def _status_to_code(status_code: int, detail: str = "") -> str:
    if detail == "RATE_LIMIT_EXCEEDED":
        return "RATE_LIMIT_EXCEEDED"
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
    }
    return mapping.get(
        status_code, "INTERNAL_ERROR" if status_code >= 500 else "CLIENT_ERROR"
    )


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom 429 handler that returns JSON matching our error envelope."""
    rid = _get_request_id(request)
    retry_after = exc.detail.split("per")[-1].strip() if exc.detail else "60"
    return _build_error_response(
        429,
        "Too many requests. Please slow down and try again.",
        code="RATE_LIMIT_EXCEEDED",
        request_id=rid,
        extra_headers={"Retry-After": retry_after},
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
        timestamps = [t for t in _memory_rate_limits[key] if now - t < window_seconds]

        if not timestamps:
            _memory_rate_limits.pop(key, None)
        else:
            _memory_rate_limits[key] = timestamps

        if len(timestamps) >= max_requests:
            rate_limit_logger.warning(
                f"Rate limit exceeded (in-memory fallback) on {scope} for IP {client_ip} "
                f"({len(timestamps)}/{max_requests} in {window_seconds}s)"
            )
            raise HTTPException(
                status_code=429,
                detail="RATE_LIMIT_EXCEEDED",
            )

        _memory_rate_limits[key] = [*timestamps, now]


def _check_rate_limit(
    request: Request, max_requests: int, window_seconds: int, scope: str
):
    """
    Check per-IP rate limit using Redis. Raises 429 if exceeded.
    Uses atomic INCR + EXPIRE to avoid race conditions.
    Falls back to in-memory sliding window if Redis is unavailable.
    """
    client_ip = get_real_client_ip(request)
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


def _enable_slow_callback_logging(threshold_sec: float = 0.5) -> None:
    """Monkey-patch the event loop to warn whenever a callback blocks longer than *threshold_sec*.

    This helps pinpoint synchronous code that freezes the entire FastAPI server.
    Only active when the PERF_DEBUG env var is set (to avoid overhead in production).
    """
    import os

    if not os.environ.get("PERF_DEBUG"):
        return

    _slow_log = logging.getLogger("surfsense.perf.slow")
    _slow_log.setLevel(logging.WARNING)
    if not _slow_log.handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(asctime)s [SLOW-CALLBACK] %(message)s"))
        _slow_log.addHandler(_h)
        _slow_log.propagate = False

    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = threshold_sec  # type: ignore[attr-defined]
    loop.set_debug(True)
    _slow_log.warning(
        "Event-loop slow-callback detector ENABLED (threshold=%.1fs). "
        "Set PERF_DEBUG='' to disable.",
        threshold_sec,
    )


def _start_openrouter_background_refresh() -> None:
    """Start periodic OpenRouter model refresh if integration is enabled."""
    from app.services.openrouter_integration_service import OpenRouterIntegrationService

    if not OpenRouterIntegrationService.is_initialized():
        return
    settings = config.OPENROUTER_INTEGRATION_SETTINGS
    if settings:
        interval = settings.get("refresh_interval_hours", 24)
        OpenRouterIntegrationService.get_instance().start_background_refresh(interval)


def _stop_openrouter_background_refresh() -> None:
    """Cancel the periodic OpenRouter refresh task on shutdown."""
    from app.services.openrouter_integration_service import OpenRouterIntegrationService

    if OpenRouterIntegrationService.is_initialized():
        OpenRouterIntegrationService.get_instance().stop_background_refresh()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tune GC: lower gen-2 threshold so long-lived garbage is collected
    # sooner (default 700/10/10 → 700/10/5). This reduces peak RSS
    # with minimal CPU overhead.
    gc.set_threshold(700, 10, 5)

    _enable_slow_callback_logging(threshold_sec=0.5)
    await create_db_and_tables()
    await setup_checkpointer_tables()
    initialize_openrouter_integration()
    _start_openrouter_background_refresh()
    initialize_llm_router()
    initialize_image_gen_router()
    initialize_vision_llm_router()
    try:
        await asyncio.wait_for(seed_surfsense_docs(), timeout=120)
    except TimeoutError:
        logging.getLogger(__name__).warning(
            "Surfsense docs seeding timed out after 120s — skipping. "
            "Docs will be indexed on the next restart."
        )

    log_system_snapshot("startup_complete")

    yield

    _stop_openrouter_background_refresh()
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

# Register structured global exception handlers (order matters: most specific first)
app.add_exception_handler(SurfSenseError, _surfsense_error_handler)
app.add_exception_handler(RequestValidationError, _validation_error_handler)
app.add_exception_handler(HTTPException, _http_exception_handler)
app.add_exception_handler(Exception, _unhandled_exception_handler)


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and echo it in the response."""

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# Request-level performance middleware
# ---------------------------------------------------------------------------
# Logs wall-clock time, method, path, and status for every request so we can
# spot slow endpoints in production logs.

_PERF_SLOW_REQUEST_THRESHOLD = float(
    __import__("os").environ.get("PERF_SLOW_REQUEST_MS", "2000")
)


class RequestPerfMiddleware(BaseHTTPMiddleware):
    """Middleware that logs per-request wall-clock time.

    - ALL requests are logged at DEBUG level.
    - Requests exceeding PERF_SLOW_REQUEST_MS (default 2000ms) are logged at
      WARNING level with a system snapshot so we can correlate slow responses
      with CPU/memory usage at that moment.
    """

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        perf = get_perf_logger()
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        path = request.url.path
        method = request.method
        status = response.status_code

        perf.debug(
            "[request] %s %s -> %d in %.1fms",
            method,
            path,
            status,
            elapsed_ms,
        )

        if elapsed_ms > _PERF_SLOW_REQUEST_THRESHOLD:
            perf.warning(
                "[SLOW_REQUEST] %s %s -> %d in %.1fms (threshold=%.0fms)",
                method,
                path,
                status,
                elapsed_ms,
                _PERF_SLOW_REQUEST_THRESHOLD,
            )
            log_system_snapshot("slow_request")

        return response


app.add_middleware(RequestPerfMiddleware)

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

allowed_origins.extend(
    [  # For local development and desktop app
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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


# Anonymous (no-login) chat routes — mounted at /api/v1/public/anon-chat
from app.routes.anonymous_chat_routes import (  # noqa: E402
    router as anonymous_chat_router,
)

app.include_router(anonymous_chat_router)

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
