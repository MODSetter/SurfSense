"""What a tool call returned, as the text a step shows."""

from typing import Any


def result_text(content: str | list[dict[str, Any]] | None) -> str:
    """An MCP result's text blocks, joined; its images are the model's alone."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(item["text"] for item in content if item.get("type") == "text")
