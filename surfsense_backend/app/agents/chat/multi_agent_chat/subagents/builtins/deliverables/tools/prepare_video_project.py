"""Trusted writer for Remotion project inputs."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.deliverables.jobs.policy import VIDEO_KIND, get_deliverable_kind_spec

_SCENE_FILENAME_PATTERN = r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?\.tsx$"
_PUBLIC_PATH_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,254}$"
_VIDEO_SPEC = get_deliverable_kind_spec(VIDEO_KIND)


class VideoScene(BaseModel):
    """One complete, self-contained Remotion scene module."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    slide_number: Annotated[int, Field(gt=0)]
    filename: Annotated[str, Field(pattern=_SCENE_FILENAME_PATTERN)]
    code: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100_000,
            description=(
                "Complete self-contained TSX module, including its imports and "
                "exactly one default component export"
            ),
        ),
    ]
    audio: Annotated[str | None, Field(pattern=_PUBLIC_PATH_PATTERN)] = None

    @field_validator("audio")
    @classmethod
    def public_relative_audio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("scene audio must be a public-relative path")
        return value


class VideoProject(BaseModel):
    """Typed input consumed by the Remotion harness."""

    model_config = ConfigDict(extra="forbid")

    fps: Annotated[int, Field(ge=1, le=120)] = 30
    min_duration_in_frames: Annotated[int, Field(gt=0)] = 30
    scenes: Annotated[
        list[VideoScene],
        Field(min_length=1, max_length=_VIDEO_SPEC.max_scenes),
    ]

    @model_validator(mode="after")
    def unique_scene_identity(self) -> VideoProject:
        slide_numbers = [scene.slide_number for scene in self.scenes]
        filenames = [scene.filename for scene in self.scenes]
        if len(set(slide_numbers)) != len(slide_numbers):
            raise ValueError("scene slide_number values must be unique")
        if len(set(filenames)) != len(filenames):
            raise ValueError("scene filenames must be unique")
        return self


def _validate_project_policy(project: VideoProject) -> None:
    if len(project.scenes) > _VIDEO_SPEC.max_scenes:
        raise ValueError(
            f"video projects support at most {_VIDEO_SPEC.max_scenes} scenes"
        )


async def prepare_video_project(
    project: VideoProject,
    *,
    session,
    workdir: PurePosixPath,
) -> dict:
    """Write one validated project into an already-owned sandbox workdir."""
    _validate_project_policy(project)
    props_path = workdir / "props.json"
    payload = json.dumps(
        project.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    await session.write_file(str(props_path), payload)
    return {
        "status": "prepared",
        "workdir": str(workdir),
        "props_path": str(props_path),
        "scene_count": len(project.scenes),
        "scene_files": [scene.filename for scene in project.scenes],
    }
