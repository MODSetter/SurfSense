"""The bundled stable-diffusion.cpp server: local image generation."""

from modules.llm.providers.sdcpp.provider import (
    CATALOG,
    PROVIDER,
    ImageModel,
    base_url,
    find,
    install,
    installed,
    offered,
    path_of,
    remove,
)

__all__ = [
    "CATALOG",
    "PROVIDER",
    "ImageModel",
    "base_url",
    "find",
    "install",
    "installed",
    "offered",
    "path_of",
    "remove",
]
