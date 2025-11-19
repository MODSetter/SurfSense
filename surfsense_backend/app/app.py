from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import config
from app.db import SiteConfiguration, User, create_db_and_tables, get_async_session
from app.routes import router as crud_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.users import SECRET, auth_backend, current_active_user, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()
    yield


async def registration_allowed(session: AsyncSession = Depends(get_async_session)):
    # Check environment variable first
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled by system configuration"
        )

    # Check site configuration database toggle
    result = await session.execute(select(SiteConfiguration).where(SiteConfiguration.id == 1))
    site_config = result.scalar_one_or_none()

    if site_config and site_config.disable_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled. Please contact the administrator if you need access."
        )

    return True


app = FastAPI(lifespan=lifespan)

# Add ProxyHeaders middleware FIRST to trust proxy headers (e.g., from Cloudflare)
# This ensures FastAPI uses HTTPS in redirects when behind a proxy
# SECURITY: Only trust specific proxy hosts in production
# Set TRUSTED_HOSTS env var to comma-separated list of trusted proxy IPs
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=config.TRUSTED_HOSTS)

# Add CORS middleware
# SECURITY: Restrict to specific methods and headers for better security
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # Configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(registration_allowed)],  # blocks registration when disabled
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
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

if config.AUTH_TYPE == "GOOGLE":
    from app.users import google_oauth_client

    app.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client, auth_backend, SECRET, is_verified_by_default=True
        )
        if not config.BACKEND_URL
        else fastapi_users.get_oauth_router(
            google_oauth_client,
            auth_backend,
            SECRET,
            is_verified_by_default=True,
            redirect_url=f"{config.BACKEND_URL}/auth/google/callback",
        ),
        prefix="/auth/google",
        tags=["auth"],
        dependencies=[
            Depends(registration_allowed)
        ],  # blocks OAuth registration when disabled
    )

app.include_router(crud_router, prefix="/api/v1", tags=["crud"])


@app.get("/verify-token")
async def authenticated_route(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return {
        "message": "Token is valid",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "is_verified": user.is_verified,
        }
    }
