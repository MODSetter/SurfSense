"""
Image compression service for SurfSense.
Compresses images to reduce file size while maintaining quality.
"""

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


class ImageCompressionService:
    """Service for compressing images with configurable quality levels."""

    # Compression settings for different quality levels
    COMPRESSION_SETTINGS = {
        "low": {
            "max_width": 800,
            "max_height": 800,
            "quality": 60,
            "format": "webp",
        },
        "medium": {
            "max_width": 1200,
            "max_height": 1200,
            "quality": 75,
            "format": "webp",
        },
        "high": {
            "max_width": 1920,
            "max_height": 1920,
            "quality": 85,
            "format": "webp",
        },
        "none": {
            "max_width": None,
            "max_height": None,
            "quality": None,
            "format": None,
        },
    }

    def __init__(self, temp_dir: str = "/tmp/surfsense/compressed"):
        """
        Initialize the image compression service.

        Args:
            temp_dir: Directory for temporary compressed files
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_compression_settings(self, level: str) -> dict:
        """
        Get compression settings for a given quality level.

        Args:
            level: Compression level (low, medium, high, none)

        Returns:
            Dictionary with compression settings
        """
        if level not in self.COMPRESSION_SETTINGS:
            logger.warning(f"Invalid compression level '{level}', using 'medium'")
            level = "medium"

        return self.COMPRESSION_SETTINGS[level]

    def compress_image(
        self, input_path: str, level: str = "medium", output_path: Optional[str] = None
    ) -> Tuple[str, dict]:
        """
        Compress an image file.

        Args:
            input_path: Path to the input image
            level: Compression level (low, medium, high, none)
            output_path: Optional output path. If None, generates a temporary file.

        Returns:
            Tuple of (output_path, metadata) where metadata contains:
                - original_size: Original file size in bytes
                - compressed_size: Compressed file size in bytes
                - compression_ratio: Compression ratio as percentage
                - original_format: Original image format
                - compressed_format: Compressed image format
                - original_dimensions: Original image dimensions (width, height)
                - compressed_dimensions: Compressed image dimensions (width, height)

        Raises:
            ValueError: If the input file is not a valid image format
            RuntimeError: If image compression fails for other reasons
            FileNotFoundError: If the input file doesn't exist
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Get original file size
        original_size = input_path.stat().st_size

        # Get compression settings
        settings = self.get_compression_settings(level)

        try:
            # If level is "none", just copy the file
            if level == "none":
                # Validate image first before file operations to prevent temp file creation on error
                with Image.open(input_path) as img:
                    original_format = img.format
                    dimensions = img.size

                if output_path is None:
                    output_path = self.temp_dir / f"no_compression_{input_path.name}"
                else:
                    output_path = Path(output_path)

                # Copy file without compression using chunk-based I/O for memory efficiency
                # Wrap in try-except to clean up partial files on copy failure
                try:
                    with open(input_path, "rb") as src, open(output_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                except OSError as e:
                    # Clean up partial output file if copy failed
                    if output_path.exists():
                        try:
                            output_path.unlink()
                        except OSError as unlink_error:
                            logger.warning(f"Could not delete partial file {output_path}: {unlink_error}")
                    logger.error(f"Failed to copy file {input_path}: {e}")
                    raise RuntimeError(f"File copy operation failed: {e}") from e

                # Reuse original_size since no compression occurred
                compressed_size = original_size

                return str(output_path), {
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": 0.0,
                    "original_format": original_format,
                    "compressed_format": original_format,
                    "original_dimensions": dimensions,
                    "compressed_dimensions": dimensions,
                }

            # Open and process image
            with Image.open(input_path) as img:
                original_format = img.format
                original_dimensions = img.size

                # Convert RGBA to RGB if saving as JPEG or WebP
                if img.mode in ("RGBA", "LA", "P"):
                    if settings["format"] in ("jpeg", "jpg"):
                        # Create white background for JPEG
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                        img = background
                    elif settings["format"] == "webp":
                        # WebP supports transparency
                        img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

                # Resize if needed
                if settings["max_width"] and settings["max_height"]:
                    img.thumbnail(
                        (settings["max_width"], settings["max_height"]),
                        Image.Resampling.LANCZOS,
                    )

                compressed_dimensions = img.size

                # Generate output path if not provided
                if output_path is None:
                    # Generate unique filename using UUID to avoid collisions
                    output_filename = f"compressed_{uuid.uuid4().hex[:16]}.{settings['format']}"
                    output_path = self.temp_dir / output_filename
                else:
                    output_path = Path(output_path)

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Save compressed image with error handling for partial file cleanup
                save_kwargs = {}
                if settings["format"] == "webp":
                    save_kwargs = {
                        "format": "WebP",
                        "quality": settings["quality"],
                        "method": 6,  # Best compression
                    }
                elif settings["format"] in ("jpeg", "jpg"):
                    save_kwargs = {
                        "format": "JPEG",
                        "quality": settings["quality"],
                        "optimize": True,
                    }
                elif settings["format"] == "png":
                    save_kwargs = {
                        "format": "PNG",
                        "optimize": True,
                    }

                try:
                    img.save(output_path, **save_kwargs)
                except OSError as e:
                    # Clean up partial output file if save failed
                    if output_path.exists():
                        try:
                            output_path.unlink()
                        except OSError as unlink_error:
                            logger.warning(f"Could not delete partial file {output_path}: {unlink_error}")
                    logger.error(f"Failed to save compressed image {output_path}: {e}")
                    raise RuntimeError(f"Image save operation failed: {e}") from e

            # Get compressed file size
            compressed_size = output_path.stat().st_size

            # Calculate compression ratio
            compression_ratio = (
                ((original_size - compressed_size) / original_size) * 100
                if original_size > 0
                else 0.0
            )

            metadata = {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": round(compression_ratio, 2),
                "original_format": original_format,
                "compressed_format": settings["format"] or original_format,
                "original_dimensions": original_dimensions,
                "compressed_dimensions": compressed_dimensions,
            }

            logger.info(
                f"Compressed image: {input_path.name} -> {output_path.name} "
                f"({original_size} bytes -> {compressed_size} bytes, "
                f"{compression_ratio:.1f}% reduction)"
            )

            return str(output_path), metadata

        except UnidentifiedImageError as e:
            # Client error: uploaded file is not a valid/supported image format
            logger.warning(f"Attempted to compress invalid image file: {input_path}")
            raise ValueError("Invalid or unsupported image file format") from e
        except Exception as e:
            # Server error: compression failed for reasons other than invalid format
            logger.error(f"Error compressing image {input_path}: {e}")
            raise RuntimeError(str(e)) from e

    def calculate_compression_ratio(
        self, original_size: int, compressed_size: int
    ) -> float:
        """
        Calculate compression ratio as percentage.

        Args:
            original_size: Original file size in bytes
            compressed_size: Compressed file size in bytes

        Returns:
            Compression ratio as percentage (e.g., 45.5 for 45.5% reduction)
        """
        if original_size == 0:
            return 0.0
        return ((original_size - compressed_size) / original_size) * 100


# Global service instance
_image_compression_service: Optional[ImageCompressionService] = None


def get_image_compression_service() -> ImageCompressionService:
    """
    Get or create the global image compression service instance.

    Returns:
        ImageCompressionService instance
    """
    global _image_compression_service

    if _image_compression_service is None:
        _image_compression_service = ImageCompressionService()

    return _image_compression_service
