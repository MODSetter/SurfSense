"""Run one image generation against a resolved model.

Pure: no billing, no persistence, no session. Callers wrap it with whatever
metering and storage their door needs.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from litellm import aimage_generation

from app.artifacts.generation.image.resolve import ResolvedImageModel


async def run_image_generation(
    model: ResolvedImageModel,
    *,
    prompt: str,
    n: int = 1,
) -> dict[str, Any]:
    """Call the provider and return a normalized response dict.

    Provider-relative image URLs are rewritten to absolute using the model's
    base URL, since the bytes are fetched later from a different host.
    """
    gen_kwargs: dict[str, Any] = dict(model.gen_kwargs)
    if n and n > 1:
        gen_kwargs["n"] = n

    response = await aimage_generation(
        prompt=prompt, model=model.model_string, **gen_kwargs
    )

    response_dict = (
        response.model_dump() if hasattr(response, "model_dump") else dict(response)
    )

    if model.provider_base_url:
        parsed = urlparse(model.provider_base_url)
        for image in response_dict.get("data") or []:
            raw_url = image.get("url") if isinstance(image, dict) else None
            if raw_url and raw_url.startswith("/"):
                image["url"] = f"{parsed.scheme}://{parsed.netloc}{raw_url}"

    return response_dict
