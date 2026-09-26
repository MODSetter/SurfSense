"""What a curated sd.cpp model commits beyond the shared entry: what it does,
and the settings sd-server is started with. An image model has `image`
defaults and a video model `video` ones; each has exactly one."""

from typing import Literal

from pydantic import BaseModel, Field

from modules.llm.catalog.local.manifest.strict import STRICT


class ImageDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    # Reviewed, not read from a file: one pipeline tag cannot say both, and
    # FLUX.2 klein's GGUF repo is tagged text-to-image while it edits too.
    tasks: list[Literal["generate", "edit"]] = Field(
        default_factory=lambda: ["generate"], min_length=1
    )
    resolution: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    flow_shift: float | None = None


class VideoDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    # What a clip starts from: text, and for some models an image too.
    tasks: list[Literal["text", "image"]] = Field(
        default_factory=lambda: ["text"], min_length=1
    )
    width: int | None = None
    height: int | None = None
    # Wan takes a multiple of four plus one.
    frames: int | None = None
    fps: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    flow_shift: float | None = None


ENTRY_OWNS = frozenset({"image", "video"})
ENTRY_REQUIRES: frozenset[str] = frozenset()
# One of these, never both: what the model makes decides its settings.
ENTRY_REQUIRES_ONE_OF = frozenset({"image", "video"})
