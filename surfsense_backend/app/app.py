from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import User, create_db_and_tables, get_async_session
from app.routes import router as crud_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.users import SECRET, auth_backend, current_active_user, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()
    yield


def registration_allowed():
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled"
        )
    return True


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
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
    from app.users import google_oauth_client

    app.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client, auth_backend, SECRET, is_verified_by_default=True
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
    return {"message": "Token is valid"}
