import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import User, create_db_and_tables, get_async_session
from app.routes import router as crud_router
from app.routes.scheduler_routes import router as scheduler_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.services.connector_scheduler_service import start_scheduler, stop_scheduler
from app.users import SECRET, auth_backend, current_active_user, fastapi_users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with scheduler integration."""
    # Startup
    logger.info("Starting SurfSense application...")
    
    # Create database tables
    await create_db_and_tables()
    logger.info("Database tables created/verified")
    
    # Start the connector scheduler service
    scheduler_task = asyncio.create_task(start_scheduler())
    logger.info("Connector scheduler service started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down SurfSense application...")
    
    # Stop the scheduler service
    await stop_scheduler()
    logger.info("Connector scheduler service stopped")
    
    # Cancel the scheduler task
    if not scheduler_task.done():
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Application shutdown complete")


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
    )

app.include_router(crud_router, prefix="/api/v1", tags=["crud"])
app.include_router(scheduler_router, prefix="/api/v1", tags=["scheduler"])


@app.get("/verify-token")
async def authenticated_route(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return {"message": "Token is valid"}
