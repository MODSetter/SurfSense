"""Trusted infographic image generation and PNG normalization."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.image.bytes import image_bytes_from_response
from app.artifacts.media.image.generation import generate_image_response

from .prompt import assemble_infographic_prompt
from .schemas import VisualStylePreset

MAX_IMAGE_DIMENSION = 8_192
MAX_IMAGE_PIXELS = 40_000_000


@dataclass(frozen=True, slots=True)
class GeneratedInfographic:
    png: bytes
    width: int
    height: int
    image_gen_model_id: int
    provider_model: str | None

    def provenance(self) -> dict[str, Any]:
        return {
            "image_gen_model_id": self.image_gen_model_id,
            "provider_model": self.provider_model,
            "width": self.width,
            "height": self.height,
        }


def normalize_infographic_png(data: bytes) -> tuple[bytes, int, int]:
    """Fail closed on unsafe image features and return bounded RGB PNG bytes."""
    try:
        with Image.open(BytesIO(data)) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Infographic output must not be animated")
            width, height = image.size
            if (
                width < 256
                or height < 256
                or width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise ValueError("Infographic output dimensions are unsupported")
            if "A" in image.getbands():
                alpha = image.getchannel("A")
                if alpha.getextrema() != (255, 255):
                    raise ValueError("Infographic output must not be transparent")
            rgb = image.convert("RGB")
            output = BytesIO()
            rgb.save(output, format="PNG", optimize=True)
    except (Image.DecompressionBombError, UnidentifiedImageError) as exc:
        raise ValueError("Image provider returned an invalid image") from exc
    png = output.getvalue()
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Infographic output could not be normalized to PNG")
    return png, width, height


async def generate_infographic(
    session: AsyncSession,
    *,
    workspace_id: int,
    factual_content: str,
    style: VisualStylePreset,
    output_constraints: str | None = None,
    repair_findings: tuple[str, ...] = (),
) -> GeneratedInfographic:
    """Invoke the shared service after HITL and normalize its first image."""
    prompt = assemble_infographic_prompt(
        factual_content=factual_content,
        style=style,
        output_constraints=output_constraints,
        repair_findings=repair_findings,
    )
    generated = await generate_image_response(
        session,
        workspace_id=workspace_id,
        prompt=prompt,
        n=1,
        usage_type="infographic_generation",
    )
    raw, _mime_type, _extension = await image_bytes_from_response(generated.response)
    png, width, height = normalize_infographic_png(raw)
    return GeneratedInfographic(
        png=png,
        width=width,
        height=height,
        image_gen_model_id=generated.config_id,
        provider_model=generated.provider_model,
    )


__all__ = [
    "GeneratedInfographic",
    "generate_infographic",
    "normalize_infographic_png",
]
