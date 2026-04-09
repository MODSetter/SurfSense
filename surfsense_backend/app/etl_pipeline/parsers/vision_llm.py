import asyncio
import base64
import os

from langchain_core.messages import HumanMessage

_PROMPT = (
    "Describe this image in markdown. "
    "Transcribe any visible text verbatim. "
    "Be concise but complete — let the image content guide the level of detail."
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


async def parse_with_vision_llm(file_path: str, filename: str, llm) -> str:
    data_url = _image_to_data_url(file_path)
    message = HumanMessage(
        content=[
            {"type": "text", "text": _PROMPT},
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
