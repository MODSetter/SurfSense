"""The bundled stable-diffusion.cpp server: local image generation."""

from modules.llm.providers.sdcpp.provider import PROVIDER, base_url, offered

__all__ = ["PROVIDER", "base_url", "offered"]
