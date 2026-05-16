import asyncio
import base64
import os

from langchain_core.messages import HumanMessage

# Single-shot prompt used by standalone image uploads (.png/.jpg/etc).
# A standalone image IS the document, so we want everything: visual
# content plus any text the model can read off it. The output is
# combined markdown that the chunker treats as the full document body.
_PROMPT = (
    "Describe this image in markdown. "
    "Transcribe any visible text verbatim. "
    "Be concise but complete — let the image content guide the level of detail."
)

# Per-image-in-PDF prompt. Here the image is *inside* a larger
# document, and the ETL service (Docling/Azure DI/LlamaCloud/...) is
# already running OCR over the whole page — including text rendered
# into images. So we explicitly tell the model NOT to transcribe text
# and to focus only on visual interpretation. This avoids paying
# output tokens for OCR content the ETL pipeline already captured.
_DESCRIPTION_PROMPT = (
    "Describe what this image visually depicts in concise markdown. "
    "Focus on visual content — anatomy, structures, charts, diagrams, "
    "spatial relationships, colors, modality (e.g. axial CT, ECG strip, "
    "histology slide), and any clinically or structurally relevant "
    "findings.\n\n"
    "Do NOT transcribe text from the image. Any text in the image "
    "(axis labels, annotations, scale bars, lab values, etc.) is "
    "already extracted by a separate OCR pipeline; duplicating it "
    "here would be redundant. Stick to the visual interpretation."
)

_MAX_IMAGE_BYTES = (
    5 * 1024 * 1024
)  # 5 MB (Anthropic Claude's limit, the most restrictive)

_INVOKE_TIMEOUT_SECONDS = 120

_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def _image_to_data_url(file_path: str) -> str:
    file_size = os.path.getsize(file_path)
    if file_size > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large for vision LLM ({file_size / (1024 * 1024):.1f} MB, "
            f"limit {_MAX_IMAGE_BYTES // (1024 * 1024)} MB): {file_path}"
        )
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = _EXT_TO_MIME.get(ext)
    if not mime_type:
        raise ValueError(f"Unsupported image extension {ext!r}: {file_path}")
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def _invoke_vision(llm, prompt: str, data_url: str, filename: str) -> str:
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    )
    response = await asyncio.wait_for(
        llm.ainvoke([message]), timeout=_INVOKE_TIMEOUT_SECONDS
    )
    text = response.content if hasattr(response, "content") else str(response)
    if not text or not text.strip():
        raise ValueError(f"Vision LLM returned empty content for {filename}")
    return text.strip()


async def parse_with_vision_llm(file_path: str, filename: str, llm) -> str:
    """Single-shot: returns combined markdown for a standalone image upload.

    Used when the operator uploads an image file directly (jpg/png/etc).
    The image is the document, so the prompt asks for both visual
    description and verbatim text in one go.
    """
    data_url = _image_to_data_url(file_path)
    return await _invoke_vision(llm, _PROMPT, data_url, filename)


async def parse_image_for_description(file_path: str, filename: str, llm) -> str:
    """Visual-description-only call for per-image-in-PDF use.

    Used by ``picture_describer`` when an image is embedded inside a
    larger document. Returns a markdown description of what the image
    visually depicts; deliberately does NOT include text-in-image OCR
    because the ETL service (Docling, Azure DI, LlamaCloud, ...) is
    already running OCR over the entire page and would duplicate that
    text content.
    """
    data_url = _image_to_data_url(file_path)
    return await _invoke_vision(llm, _DESCRIPTION_PROMPT, data_url, filename)


__all__ = [
    "parse_image_for_description",
    "parse_with_vision_llm",
]
