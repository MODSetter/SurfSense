import asyncio
import gc
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
    initialize_vision_llm_router,
)
from app.db import User, create_db_and_tables, get_async_session
from app.middleware.proxy_auth import ProxyAuthMiddleware
from app.routes import router as crud_router
from app.routes.auth_routes import router as auth_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.tasks.surfsense_docs_indexer import seed_surfsense_docs
from app.users import (
    current_active_user,
    fastapi_users,
    get_user_manager,
)
from app.utils.perf import get_perf_logger, log_system_snapshot

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tune GC: lower gen-2 threshold so long-lived garbage is collected
    # sooner (default 700/10/10 → 700/10/5). This reduces peak RSS
    # with minimal CPU overhead.
    gc.set_threshold(700, 10, 5)

    _enable_slow_callback_logging(threshold_sec=0.5)
    await create_db_and_tables()
    await setup_checkpointer_tables()
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

# Starlette executes middleware in reverse registration order (last added = first to
# run on the request).  Request-path execution order:
#
#   CORSMiddleware → ProxyHeadersMiddleware → SlowAPIMiddleware
#   → ProxyAuthMiddleware → RequestPerfMiddleware → route handler
#
# SlowAPIMiddleware wraps ProxyAuthMiddleware so rate limiting fires before any DB
# lookup — abusive traffic is shed at the limiter before we touch the database.
# ProxyAuthMiddleware runs after ProxyHeadersMiddleware so the client IP/scheme
# are already normalised when we resolve the user.

# Innermost: reads X-Auth-Request-Email, resolves/creates user, sets request.state.proxy_user.
app.add_middleware(ProxyAuthMiddleware)

# Wraps ProxyAuthMiddleware — rate limiting fires before the DB lookup.
# Uses Starlette BaseHTTPMiddleware (not the raw ASGI variant) to avoid
# corrupting StreamingResponse — SlowAPIASGIMiddleware re-sends
# http.response.start on every body chunk, breaking SSE/streaming endpoints.
app.add_middleware(SlowAPIMiddleware)

# Outermost of the inner three: trusts proxy headers (X-Forwarded-For etc.)
# so FastAPI uses HTTPS in redirects when behind Traefik.
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

# Register /users/me BEFORE fastapi_users.get_users_router so our routes take
# precedence (FastAPI first-match wins). fastapi-users' internal /users/me only
# validates JWT — it does not check request.state.proxy_user set by the proxy
# auth middleware, so proxy-auth users would always get 401 from that route.
@app.get("/users/me", response_model=UserRead, tags=["users"])
async def get_current_user_me(user: User = Depends(current_active_user)):
    return user


@app.patch("/users/me", response_model=UserRead, tags=["users"])
async def update_current_user_me(
    request: Request,
    user_update: UserUpdate,
    user: User = Depends(current_active_user),
    user_manager=Depends(get_user_manager),
):
    return await user_manager.update(user_update, user, safe=True, request=request)


app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


# Include custom auth routes (refresh token, logout)
app.include_router(auth_router)


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
