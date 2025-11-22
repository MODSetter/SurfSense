"""Schemas for media compression."""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class CompressionSettings(BaseModel):
    """User's compression preference settings."""

    image_compression_level: Literal["low", "medium", "high", "none"] = Field(
        default="medium",
        description="Image compression level",
    )
    video_compression_level: Literal["low", "medium", "high", "none"] = Field(
        default="medium",
        description="Video compression level",
    )
    auto_compress_enabled: bool = Field(
        default=True,
        description="Whether to automatically compress media on upload",
    )


class CompressionMetadata(BaseModel):
    """Metadata about a compression operation."""

    original_size: int = Field(..., description="Original file size in bytes")
    compressed_size: int = Field(..., description="Compressed file size in bytes")
    compression_ratio: float = Field(..., description="Compression ratio as percentage")
    original_format: Optional[str] = Field(None, description="Original file format")
    compressed_format: Optional[str] = Field(None, description="Compressed file format")


class ImageCompressionMetadata(CompressionMetadata):
    """Metadata about an image compression operation."""

    original_dimensions: tuple[int, int] = Field(
        ..., description="Original image dimensions (width, height)"
    )
    compressed_dimensions: tuple[int, int] = Field(
        ..., description="Compressed image dimensions (width, height)"
    )


class VideoCompressionMetadata(CompressionMetadata):
    """Metadata about a video compression operation."""

    original_metadata: dict = Field(..., description="Original video metadata")
    compressed_metadata: dict = Field(..., description="Compressed video metadata")


class CompressionResponse(BaseModel):
    """Response from a compression operation."""

    success: bool = Field(..., description="Whether the compression was successful")
    message: str = Field(..., description="Status message")
    file_path: Optional[str] = Field(None, description="Path to the compressed file")
    metadata: Optional[Union[ImageCompressionMetadata, VideoCompressionMetadata, CompressionMetadata]] = Field(
        None, description="Compression metadata"
    )


class CompressionProgress(BaseModel):
    """Progress update for a compression operation."""

    progress: float = Field(..., description="Progress percentage (0-100)")
    message: str = Field(..., description="Progress message")
    status: Literal["processing", "completed", "error"] = Field(
        ..., description="Current status"
    )
