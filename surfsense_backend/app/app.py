from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.agents.new_chat.checkpointer import (
    close_checkpointer,
    setup_checkpointer_tables,
)
from app.config import config, initialize_llm_router
from app.db import User, create_db_and_tables, get_async_session
from app.routes import router as crud_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.tasks.surfsense_docs_indexer import seed_surfsense_docs
from app.users import SECRET, auth_backend, current_active_user, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()
    # Setup LangGraph checkpointer tables for conversation persistence
    await setup_checkpointer_tables()
    # Initialize LLM Router for Auto mode load balancing
    initialize_llm_router()
    # Seed Surfsense documentation
    await seed_surfsense_docs()
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


@app.get("/verify-token")
async def authenticated_route(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return {"message": "Token is valid"}
