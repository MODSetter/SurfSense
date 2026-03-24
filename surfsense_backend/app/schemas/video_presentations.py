"""Video presentation schemas for API responses."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class VideoPresentationStatusEnum(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class VideoPresentationBase(BaseModel):
    """Base video presentation schema."""

    title: str
    slides: list[dict[str, Any]] | None = None
    scene_codes: list[dict[str, Any]] | None = None
    search_space_id: int


class VideoPresentationCreate(VideoPresentationBase):
    """Schema for creating a video presentation."""

    pass


class VideoPresentationUpdate(BaseModel):
    """Schema for updating a video presentation."""

    title: str | None = None
    slides: list[dict[str, Any]] | None = None
    scene_codes: list[dict[str, Any]] | None = None


class VideoPresentationRead(VideoPresentationBase):
    """Schema for reading a video presentation."""

    id: int
    status: VideoPresentationStatusEnum = VideoPresentationStatusEnum.READY
    created_at: datetime
    slide_count: int | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_slides(cls, obj):
        """Create VideoPresentationRead with slide_count computed.

        Replaces raw server file paths in `audio_file` with API streaming
        URLs so the frontend can use them directly in Remotion <Audio />.
        """
        slides = obj.slides
        if slides:
            slides = _replace_audio_paths_with_urls(obj.id, slides)

        data = {
            "id": obj.id,
            "title": obj.title,
            "slides": slides,
            "scene_codes": obj.scene_codes,
            "search_space_id": obj.search_space_id,
            "status": obj.status,
            "created_at": obj.created_at,
            "slide_count": len(obj.slides) if obj.slides else None,
        }
        return cls(**data)


def _replace_audio_paths_with_urls(
    video_presentation_id: int,
    slides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace server-local audio_file paths with streaming API URLs.

    Transforms:
      "audio_file": "video_presentation_audio/abc_slide_1.mp3"
    Into:
      "audio_url": "/api/v1/video-presentations/42/slides/1/audio"

    The frontend passes this URL to Remotion's <Audio src={slide.audio_url} />.
    """
    result = []
    for slide in slides:
        slide_copy = dict(slide)
        slide_number = slide_copy.get("slide_number")
        audio_file = slide_copy.pop("audio_file", None)

        if audio_file and slide_number is not None:
            slide_copy["audio_url"] = (
                f"/api/v1/video-presentations/{video_presentation_id}"
                f"/slides/{slide_number}/audio"
            )
        else:
            slide_copy["audio_url"] = None

        result.append(slide_copy)
    return result
