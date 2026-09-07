import base64
import binascii
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.llm.credentials import read_provider_key
from shared.config import get_llm_settings
from worker.studio.builders import Built, Source

# Image generation runs for a while; auth is quick.
TIMEOUT = httpx.Timeout(180.0, connect=5.0)
GROUNDING_CHARS = 6_000

# The visual formats and how each frames the image request.
_INSTRUCTIONS = {
    "image": "Create a single illustrative image that captures the sources below.",
    "infographic": (
        "Design a clear infographic that summarises the key facts and figures "
        "in the sources below."
    ),
}


def render(
    session: Session, fmt: str, sources: list[Source], user_prompt: str | None
) -> Built:
    """Ask the BYO OpenRouter image model to draw the format, and store the PNG.

    No local builder: the model returns the bytes and they are saved as-is. The
    key is required (the API gates this format on it), re-checked here so a
    worker run without one fails with a reason rather than a 401 from upstream.
    """
    key = read_provider_key(session, "openrouter")
    if not key:
        raise RuntimeError("no OpenRouter API key; set one in model settings")

    instruction = _INSTRUCTIONS.get(fmt, _INSTRUCTIONS["image"])
    if user_prompt:
        instruction += f" Emphasise: {user_prompt}."
    grounding = "\n\n".join(f"{s.title}: {s.content}" for s in sources)[
        :GROUNDING_CHARS
    ]

    data = _request_image(key, f"{instruction}\n\n{grounding}")
    png = _first_image(data)

    title = (user_prompt or fmt).strip()[:200] or "Image"
    return Built(
        title=title,
        markdown=f"# {title}\n\n{instruction}",
        primary=png,
        primary_mime="image/png",
        primary_filename=f"{fmt}.png",
    )


def _request_image(key: str, content: str) -> dict[str, Any]:
    settings = get_llm_settings()
    body = {
        "model": settings.openrouter_image_model,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"Authorization": f"Bearer {key}", "X-Title": "SurfSense"}
    with httpx.Client(
        base_url=settings.openrouter_base_url.rstrip("/"),
        timeout=TIMEOUT,
        headers=headers,
    ) as client:
        reply = client.post("/chat/completions", json=body)
        reply.raise_for_status()
        return reply.json()


def _first_image(data: dict[str, Any]) -> bytes:
    """The first image OpenRouter returned, decoded from its data URL."""
    choices = data.get("choices") or []
    images = (choices[0].get("message") or {}).get("images") or [] if choices else []
    for image in images:
        url = (image.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            try:
                return base64.b64decode(url.split(",", 1)[-1])
            except (binascii.Error, ValueError):
                continue
    raise RuntimeError("the model returned no image")
