"""
Video compression service for SurfSense.
Compresses videos using FFmpeg to reduce file size while maintaining quality.
"""

import asyncio
import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)


class VideoCompressionService:
    """Service for compressing videos with configurable quality levels."""

    # Compression settings for different quality levels
    COMPRESSION_SETTINGS = {
        "low": {
            "resolution": "480p",
            "height": 480,
            "bitrate": "500k",
            "audio_bitrate": "64k",
            "codec": "libx264",
            "preset": "fast",
            "crf": 28,  # Constant Rate Factor (lower = better quality, 18-28 is reasonable)
        },
        "medium": {
            "resolution": "720p",
            "height": 720,
            "bitrate": "1500k",
            "audio_bitrate": "128k",
            "codec": "libx264",
            "preset": "medium",
            "crf": 23,
        },
        "high": {
            "resolution": "1080p",
            "height": 1080,
            "bitrate": "3000k",
            "audio_bitrate": "192k",
            "codec": "libx264",
            "preset": "slow",
            "crf": 20,
        },
        "none": {
            "resolution": None,
            "height": None,
            "bitrate": None,
            "audio_bitrate": None,
            "codec": None,
            "preset": None,
            "crf": None,
        },
    }

    def __init__(self, temp_dir: str = "/tmp/surfsense/compressed"):
        """
        Initialize the video compression service.

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

    async def check_ffmpeg_installed(self) -> bool:
        """
        Check if FFmpeg is installed and accessible.

        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.wait(), timeout=5.0)
            return process.returncode == 0
        except (asyncio.TimeoutError, FileNotFoundError, Exception):
            return False

    async def extract_video_metadata(self, video_path: str) -> dict:
        """
        Extract metadata from a video file using ffprobe.

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary with video metadata (duration, resolution, codec, etc.)
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                video_path,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"ffprobe error: {stderr.decode()}")
                return {}

            data = json.loads(stdout.decode())

            # Extract video stream info
            video_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "video"),
                None,
            )

            # Extract audio stream info
            audio_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "audio"),
                None,
            )

            metadata = {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "size": int(data.get("format", {}).get("size", 0)),
                "format": data.get("format", {}).get("format_name", ""),
            }

            if video_stream:
                metadata.update(
                    {
                        "width": int(video_stream.get("width", 0)),
                        "height": int(video_stream.get("height", 0)),
                        "video_codec": video_stream.get("codec_name", ""),
                        "video_bitrate": int(video_stream.get("bit_rate", 0)),
                        "frame_rate": eval(video_stream.get("r_frame_rate", "0/1")),
                    }
                )

            if audio_stream:
                metadata.update(
                    {
                        "audio_codec": audio_stream.get("codec_name", ""),
                        "audio_bitrate": int(audio_stream.get("bit_rate", 0)),
                        "sample_rate": int(audio_stream.get("sample_rate", 0)),
                    }
                )

            return metadata

        except Exception as e:
            logger.error(f"Error extracting video metadata: {e}")
            return {}

    async def compress_video(
        self,
        input_path: str,
        level: str = "medium",
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[str, dict]:
        """
        Compress a video file using FFmpeg.

        Args:
            input_path: Path to the input video
            level: Compression level (low, medium, high, none)
            output_path: Optional output path. If None, generates a temporary file.
            progress_callback: Optional callback function(progress_percent, message)

        Returns:
            Tuple of (output_path, metadata) where metadata contains:
                - original_size: Original file size in bytes
                - compressed_size: Compressed file size in bytes
                - compression_ratio: Compression ratio as percentage
                - original_metadata: Original video metadata
                - compressed_metadata: Compressed video metadata

        Raises:
            RuntimeError: If FFmpeg is not installed or compression fails
            FileNotFoundError: If the input file doesn't exist
        """
        if not self.check_ffmpeg_installed():
            raise RuntimeError("FFmpeg is not installed or not accessible")

        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Get original file size and metadata
        original_size = input_path.stat().st_size
        original_metadata = await self.extract_video_metadata(str(input_path))

        # Get compression settings
        settings = self.get_compression_settings(level)

        # If level is "none", just copy the file
        if level == "none":
            if output_path is None:
                output_path = self.temp_dir / f"no_compression_{input_path.name}"
            else:
                output_path = Path(output_path)

            # Copy file without compression
            with open(input_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())

            compressed_size = output_path.stat().st_size

            return str(output_path), {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": 0.0,
                "original_metadata": original_metadata,
                "compressed_metadata": original_metadata,
            }

        # Generate output path if not provided
        if output_path is None:
            # Generate unique filename using UUID to avoid collisions
            output_filename = f"compressed_{uuid.uuid4().hex[:16]}.mp4"
            output_path = self.temp_dir / output_filename
        else:
            output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command
        cmd = ["ffmpeg", "-i", str(input_path), "-y"]  # -y to overwrite output file

        # Add video codec and settings
        cmd.extend(["-c:v", settings["codec"]])
        cmd.extend(["-preset", settings["preset"]])
        cmd.extend(["-crf", str(settings["crf"])])

        # Add resolution scaling if needed
        if settings["height"]:
            cmd.extend(["-vf", f"scale=-2:{settings['height']}"])

        # Add video bitrate
        if settings["bitrate"]:
            cmd.extend(["-b:v", settings["bitrate"]])

        # Add audio codec and bitrate
        cmd.extend(["-c:a", "aac"])
        cmd.extend(["-b:a", settings["audio_bitrate"]])

        # Add output path
        cmd.append(str(output_path))

        logger.info(f"Compressing video with command: {' '.join(cmd)}")

        try:
            # Run FFmpeg with progress tracking
            if progress_callback:
                progress_callback(0, "Starting video compression...")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Read stderr for progress (FFmpeg outputs to stderr)
            stderr_output = []
            while True:
                line = await process.stderr.readline()
                if not line:
                    break

                line_str = line.decode().strip()
                stderr_output.append(line_str)

                # Parse progress from FFmpeg output
                if "time=" in line_str and original_metadata.get("duration"):
                    try:
                        # Extract time from "time=HH:MM:SS.MS"
                        time_str = line_str.split("time=")[1].split()[0]
                        h, m, s = time_str.split(":")
                        current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        progress = (
                            current_time / original_metadata["duration"]
                        ) * 100
                        progress = min(progress, 100)

                        if progress_callback:
                            progress_callback(
                                progress,
                                f"Compressing video... {progress:.1f}%",
                            )
                    except (ValueError, IndexError):
                        pass

            await process.wait()

            if process.returncode != 0:
                error_msg = "\n".join(stderr_output[-10:])  # Last 10 lines
                raise ValueError(f"FFmpeg compression failed: {error_msg}")

            if progress_callback:
                progress_callback(100, "Video compression complete!")

            # Get compressed file size and metadata
            compressed_size = output_path.stat().st_size
            compressed_metadata = await self.extract_video_metadata(str(output_path))

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
                "original_metadata": original_metadata,
                "compressed_metadata": compressed_metadata,
            }

            logger.info(
                f"Compressed video: {input_path.name} -> {output_path.name} "
                f"({original_size} bytes -> {compressed_size} bytes, "
                f"{compression_ratio:.1f}% reduction)"
            )

            return str(output_path), metadata

        except Exception as e:
            logger.error(f"Error compressing video {input_path}: {e}")
            # Clean up output file if it exists
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError as unlink_error:
                    logger.warning(f"Could not delete output file {output_path}: {unlink_error}")
            raise RuntimeError(str(e)) from e

    def estimate_compression_time(self, duration_seconds: float, level: str) -> float:
        """
        Estimate compression time based on video duration and level.

        Args:
            duration_seconds: Video duration in seconds
            level: Compression level

        Returns:
            Estimated compression time in seconds
        """
        # Rough estimates based on typical CPU performance
        # These are multipliers of the video duration
        time_multipliers = {
            "low": 0.5,  # Fast preset, processes faster than realtime
            "medium": 1.0,  # About realtime
            "high": 2.0,  # Slow preset, takes longer
            "none": 0.0,  # No compression
        }

        multiplier = time_multipliers.get(level, 1.0)
        return duration_seconds * multiplier


# Global service instance
_video_compression_service: Optional[VideoCompressionService] = None


def get_video_compression_service() -> VideoCompressionService:
    """
    Get or create the global video compression service instance.

    Returns:
        VideoCompressionService instance
    """
    global _video_compression_service

    if _video_compression_service is None:
        _video_compression_service = VideoCompressionService()

    return _video_compression_service
