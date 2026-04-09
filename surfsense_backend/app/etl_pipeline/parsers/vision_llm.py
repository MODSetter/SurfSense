import base64
import mimetypes
import os

from langchain_core.messages import HumanMessage

_PROMPT = (
    "Describe this image in markdown. "
    "Transcribe any visible text verbatim. "
    "Be concise but complete — let the image content guide the level of detail."
)

_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB (Anthropic Claude's limit, the most restrictive)


def _image_to_data_url(file_path: str) -> str:
    file_size = os.path.getsize(file_path)
    if file_size > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large for vision LLM ({file_size / (1024 * 1024):.1f} MB, "
            f"limit {_MAX_IMAGE_BYTES // (1024 * 1024)} MB): {file_path}"
        )
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"
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
    response = await llm.ainvoke([message])
    text = response.content if hasattr(response, "content") else str(response)
    if not text or not text.strip():
        raise ValueError(f"Vision LLM returned empty content for {filename}")
    return text.strip()
