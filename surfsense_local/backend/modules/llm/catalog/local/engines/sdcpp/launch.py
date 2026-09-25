"""How sd-server is launched on a build: which flag each file goes to, by the
model's family, and the model's reviewed defaults as the server's own, since
Studio posts only a prompt."""

from collections.abc import Callable

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.engines.sdcpp.manifest_fields import (
    ImageDefaults,
    VideoDefaults,
)

# These carry their VAE and text encoders inside the one file.
_ONE_FILE = frozenset({"sd1", "sdxl"})
# sd.cpp names a text encoder's flag after the encoder: an LLM for every newer
# image family, and T5 for Wan.
_T5_ENCODED = frozenset({"wan"})


def file_flags(
    architecture: str, build: Build, where: Callable[[BuildFile], str]
) -> tuple[tuple[str, str], ...]:
    """Each file's flag and where it lies in sd-server's folder."""
    return tuple((_flag(architecture, f.role), where(f)) for f in build.files)


def _flag(architecture: str, role: FileRole) -> str:
    if role is FileRole.WEIGHTS:
        return "-m" if architecture in _ONE_FILE else "--diffusion-model"
    if role is FileRole.VAE:
        return "--vae"
    if role is FileRole.TEXT_ENCODER:
        return "--t5xxl" if architecture in _T5_ENCODED else "--llm"
    return "--llm_vision"


def default_flags(image: ImageDefaults | None) -> tuple[str, ...]:
    """What the entry states; sd-server's own default for the rest."""
    if image is None:
        return ()
    flags: list[str] = []
    if image.resolution:
        flags += ["-W", str(image.resolution), "-H", str(image.resolution)]
    if image.steps:
        flags += ["--steps", str(image.steps)]
    if image.cfg is not None:
        flags += ["--cfg-scale", str(image.cfg)]
    if image.sampler:
        flags += ["--sampling-method", image.sampler]
    if image.flow_shift is not None:
        flags += ["--flow-shift", str(image.flow_shift)]
    return tuple(flags)


def video_flags(video: VideoDefaults | None) -> tuple[str, ...]:
    """A clip's size, length and rate beside the sampling a video entry states."""
    if video is None:
        return ()
    flags: list[str] = []
    if video.width and video.height:
        flags += ["-W", str(video.width), "-H", str(video.height)]
    if video.frames:
        flags += ["--video-frames", str(video.frames)]
    if video.fps:
        flags += ["--fps", str(video.fps)]
    if video.steps:
        flags += ["--steps", str(video.steps)]
    if video.cfg is not None:
        flags += ["--cfg-scale", str(video.cfg)]
    if video.sampler:
        flags += ["--sampling-method", video.sampler]
    if video.flow_shift is not None:
        flags += ["--flow-shift", str(video.flow_shift)]
    return tuple(flags)
