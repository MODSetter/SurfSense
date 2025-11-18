from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SiteConfiguration, User, get_async_session
from app.schemas.site_configuration import (
    SiteConfigurationPublic,
    SiteConfigurationRead,
    SiteConfigurationUpdate,
)
from app.users import current_active_user

router = APIRouter(prefix="/api/v1/site-config", tags=["Site Configuration"])


async def get_or_create_config(db: AsyncSession) -> SiteConfiguration:
    """Get the site configuration (singleton), creating it if it doesn't exist."""
    query = select(SiteConfiguration).where(SiteConfiguration.id == 1)
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        # Create default configuration
        config = SiteConfiguration(id=1)
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return config


@router.get("/public", response_model=SiteConfigurationPublic)
async def get_public_site_config(
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get site configuration for public use (no authentication required).
    Used by frontend to determine which UI elements to display.
    """
    config = await get_or_create_config(db)
    return config


@router.get("", response_model=SiteConfigurationRead)
async def get_site_config(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get site configuration (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    config = await get_or_create_config(db)
    return config


@router.put("", response_model=SiteConfigurationRead)
async def update_site_config(
    config_data: SiteConfigurationUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update site configuration (admin only).
    Requires authentication and superuser privileges.

    This is a singleton - there's only one site configuration record (id=1).
    All fields are optional; only provided fields will be updated.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    config = await get_or_create_config(db)

    # Update only provided fields
    update_data = config_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config
