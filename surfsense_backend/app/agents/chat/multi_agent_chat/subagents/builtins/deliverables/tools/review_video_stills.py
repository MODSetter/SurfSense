"""Bounded visual review for Remotion stills."""

from __future__ import annotations

import asyncio
import base64
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.sandbox import SandboxSession
from app.utils.structured_output import invoke_json

_MAX_STILLS = 37
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024
_MAX_EVIDENCE = 3
_VISION_TIMEOUT_SECONDS = 120
_REVIEW_PROMPT = """Review these video stills as one presentation.
Return strict JSON with clipping, overflow, contrast, hierarchy, blank_frames,
safe_margins, and summary. Each rubric item must contain a verdict of pass,
warning, or blocking plus an evidence array with at most three short,
frame-specific strings. Use blocking only when the video is unusable or
materially incomplete. Do not suggest a fixed layout or template."""


class VideoCriterionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "warning", "blocking"] = Field(
        validation_alias=AliasChoices("verdict", "status")
    )
    evidence: Annotated[
        list[Annotated[str, Field(max_length=240)]],
        Field(max_length=_MAX_EVIDENCE),
    ] = Field(default_factory=list)


class VideoStillReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clipping: VideoCriterionReview
    overflow: VideoCriterionReview
    contrast: VideoCriterionReview
    hierarchy: VideoCriterionReview = Field(
        validation_alias=AliasChoices(
            "hierarchy",
            "visual_hierarchy",
            "visualHierarchy",
        )
    )
    blank_frames: VideoCriterionReview = Field(
        validation_alias=AliasChoices("blank_frames", "blankFrames")
    )
    safe_margins: VideoCriterionReview = Field(
        validation_alias=AliasChoices("safe_margins", "safeMargins")
    )
    summary: Annotated[str, Field(max_length=500)]

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for key in ("summary", "text", "message"):
            text = value.get(key)
            if isinstance(text, str):
                return text[:500]
        evidence = value.get("evidence")
        if isinstance(evidence, list) and all(
            isinstance(item, str) for item in evidence
        ):
            return "; ".join(evidence)[:500]
        return value


def _still_path(workdir: PurePosixPath, relative_path: str) -> PurePosixPath:
    candidate = PurePosixPath(relative_path)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png"}
    ):
        raise ValueError("still paths must be relative JPEG or PNG paths")
    resolved = workdir / candidate
    if not resolved.is_relative_to(workdir):
        raise ValueError("still path escapes the queued job workdir")
    return resolved


def _validated_still_paths(
    stills: list[str], workdir: PurePosixPath
) -> list[PurePosixPath]:
    if not 1 <= len(stills) <= _MAX_STILLS:
        raise ValueError(f"stills must contain between 1 and {_MAX_STILLS} paths")
    paths = [_still_path(workdir, path) for path in stills]
    if len(set(paths)) != len(paths):
        raise ValueError("still paths must be unique")
    return paths


async def review_video_stills(
    stills: list[str],
    *,
    session: SandboxSession,
    vision_llm,
    workdir: PurePosixPath,
) -> dict[str, Any]:
    """Review explicit job-owned still paths with an explicit vision model."""
    paths = _validated_still_paths(stills, workdir)

    images = [(path, await session.read_file(str(path))) for path in paths]
    if any(len(data) > _MAX_IMAGE_BYTES for _, data in images):
        raise ValueError("a video still exceeds the 5 MiB review limit")
    if sum(len(data) for _, data in images) > _MAX_TOTAL_IMAGE_BYTES:
        raise ValueError("video stills exceed the 50 MiB review limit")
    if vision_llm is None:
        return {
            "status": "unavailable",
            "reason": "No vision-capable model is configured for this workspace",
        }

    content: list[dict[str, Any]] = [{"type": "text", "text": _REVIEW_PROMPT}]
    for path, data in images:
        content.extend(
            (
                {"type": "text", "text": f"Frame: {path.name}"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/"
                            + ("png" if path.suffix.lower() == ".png" else "jpeg")
                            + ";base64,"
                            + base64.b64encode(data).decode("ascii")
                        )
                    },
                },
            )
        )
    verdict = await asyncio.wait_for(
        invoke_json(
            vision_llm,
            [HumanMessage(content=content)],
            VideoStillReview,
        ),
        timeout=_VISION_TIMEOUT_SECONDS,
    )
    return {"status": "reviewed", "review": verdict.model_dump(mode="json")}
