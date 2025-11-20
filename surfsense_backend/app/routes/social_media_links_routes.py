from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SocialMediaLink, User, get_async_session
from app.schemas.social_media_links import (
    SocialMediaLinkCreate,
    SocialMediaLinkPublic,
    SocialMediaLinkRead,
    SocialMediaLinkUpdate,
)
from app.users import current_active_user

router = APIRouter(prefix="/social-media-links", tags=["Social Media Links"])


@router.get("/public", response_model=list[SocialMediaLinkPublic])
async def get_public_social_media_links(
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get all active social media links for public display (no authentication required).
    Returns links ordered by display_order.
    """
    query = (
        select(SocialMediaLink)
        .where(SocialMediaLink.is_active == True)
        .order_by(SocialMediaLink.display_order, SocialMediaLink.id)
    )
    result = await db.execute(query)
    links = result.scalars().all()
    return links


@router.get("", response_model=list[SocialMediaLinkRead])
async def get_all_social_media_links(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get all social media links (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = select(SocialMediaLink).order_by(
        SocialMediaLink.display_order, SocialMediaLink.id
    )
    result = await db.execute(query)
    links = result.scalars().all()
    return links


@router.post("", response_model=SocialMediaLinkRead, status_code=201)
async def create_social_media_link(
    link_data: SocialMediaLinkCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new social media link (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    new_link = SocialMediaLink(**link_data.model_dump())
    db.add(new_link)
    await db.commit()
    await db.refresh(new_link)
    return new_link


@router.get("/{link_id}", response_model=SocialMediaLinkRead)
async def get_social_media_link(
    link_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific social media link by ID (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = select(SocialMediaLink).where(SocialMediaLink.id == link_id)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Social media link not found")

    return link


@router.patch("/{link_id}", response_model=SocialMediaLinkRead)
async def update_social_media_link(
    link_id: int,
    link_data: SocialMediaLinkUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a social media link (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = select(SocialMediaLink).where(SocialMediaLink.id == link_id)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Social media link not found")

    # Update only provided fields
    update_data = link_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)

    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=204)
async def delete_social_media_link(
    link_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a social media link (admin only).
    Requires authentication and superuser privileges.
    """
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = select(SocialMediaLink).where(SocialMediaLink.id == link_id)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Social media link not found")

    await db.delete(link)
    await db.commit()
    return None
