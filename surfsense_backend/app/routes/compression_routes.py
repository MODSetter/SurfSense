"""API routes for media compression."""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.schemas import CompressionResponse, CompressionSettings
from app.services.image_compression import get_image_compression_service
from app.services.video_compression import get_video_compression_service
from app.users import current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Temporary directory for uploaded files
TEMP_UPLOAD_DIR = Path("/tmp/surfsense/uploads")
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/compress/image", response_model=CompressionResponse)
async def compress_image(
    file: UploadFile = File(...),
    level: Optional[str] = Form(None),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Compress an uploaded image file.

    Args:
        file: The image file to compress
        level: Compression level (low, medium, high, none). If None, uses user's preference.
        user: The authenticated user
        session: Database session

    Returns:
        CompressionResponse with compression metadata
    """
    try:
        # Determine compression level
        if level is None:
            # Refresh user to get latest preferences
            await session.refresh(user)
            level = user.image_compression_level

        # Validate file extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="File name is required")

        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image format: {file_ext}. "
                f"Allowed formats: {', '.join(allowed_extensions)}",
            )

        # Save uploaded file temporarily
        temp_input_path = TEMP_UPLOAD_DIR / f"upload_{user.id}_{file.filename}"
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Compress the image
        compression_service = get_image_compression_service()
        output_path, metadata = compression_service.compress_image(
            str(temp_input_path), level=level
        )

        # Clean up temporary input file
        temp_input_path.unlink()

        return CompressionResponse(
            success=True,
            message=f"Image compressed successfully ({metadata['compression_ratio']:.1f}% reduction)",
            file_path=output_path,
            metadata=metadata,
        )

    except ValueError as e:
        logger.error(f"Compression validation error: {e}")
        # Clean up temporary file if it exists
        if temp_input_path.exists():
            temp_input_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Image compression error: {e}")
        # Clean up temporary file if it exists
        if temp_input_path.exists():
            temp_input_path.unlink()
        raise HTTPException(
            status_code=500, detail=f"Failed to compress image: {str(e)}"
        )


@router.post("/compress/video", response_model=CompressionResponse)
async def compress_video(
    file: UploadFile = File(...),
    level: Optional[str] = Form(None),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Compress an uploaded video file.

    Args:
        file: The video file to compress
        level: Compression level (low, medium, high, none). If None, uses user's preference.
        user: The authenticated user
        session: Database session

    Returns:
        CompressionResponse with compression metadata
    """
    try:
        # Determine compression level
        if level is None:
            # Refresh user to get latest preferences
            await session.refresh(user)
            level = user.video_compression_level

        # Validate file extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="File name is required")

        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".wmv"}

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video format: {file_ext}. "
                f"Allowed formats: {', '.join(allowed_extensions)}",
            )

        # Check if FFmpeg is installed
        compression_service = get_video_compression_service()
        if not compression_service.check_ffmpeg_installed():
            raise HTTPException(
                status_code=500,
                detail="FFmpeg is not installed on the server. Please contact the administrator.",
            )

        # Save uploaded file temporarily
        temp_input_path = TEMP_UPLOAD_DIR / f"upload_{user.id}_{file.filename}"
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Compress the video
        output_path, metadata = await compression_service.compress_video(
            str(temp_input_path), level=level
        )

        # Clean up temporary input file
        temp_input_path.unlink()

        return CompressionResponse(
            success=True,
            message=f"Video compressed successfully ({metadata['compression_ratio']:.1f}% reduction)",
            file_path=output_path,
            metadata=metadata,
        )

    except ValueError as e:
        logger.error(f"Compression validation error: {e}")
        # Clean up temporary file if it exists
        if "temp_input_path" in locals() and temp_input_path.exists():
            temp_input_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Video compression error: {e}")
        # Clean up temporary file if it exists
        if "temp_input_path" in locals() and temp_input_path.exists():
            temp_input_path.unlink()
        raise HTTPException(
            status_code=500, detail=f"Failed to compress video: {str(e)}"
        )


@router.get("/settings", response_model=CompressionSettings)
async def get_compression_settings(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get user's compression preferences.

    Args:
        user: The authenticated user
        session: Database session

    Returns:
        CompressionSettings with user's preferences
    """
    await session.refresh(user)

    return CompressionSettings(
        image_compression_level=user.image_compression_level,
        video_compression_level=user.video_compression_level,
        auto_compress_enabled=user.auto_compress_enabled,
    )


@router.put("/settings", response_model=CompressionSettings)
async def update_compression_settings(
    settings: CompressionSettings,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update user's compression preferences.

    Args:
        settings: New compression settings
        user: The authenticated user
        session: Database session

    Returns:
        Updated CompressionSettings
    """
    try:
        # Update user settings
        user.image_compression_level = settings.image_compression_level
        user.video_compression_level = settings.video_compression_level
        user.auto_compress_enabled = settings.auto_compress_enabled

        await session.commit()
        await session.refresh(user)

        return CompressionSettings(
            image_compression_level=user.image_compression_level,
            video_compression_level=user.video_compression_level,
            auto_compress_enabled=user.auto_compress_enabled,
        )

    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating compression settings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update settings: {str(e)}"
        )
