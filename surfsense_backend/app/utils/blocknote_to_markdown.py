"""Pure-Python converter: BlockNote JSON → Markdown.

No external dependencies (no Node.js, no npm packages, no HTTP calls).
Handles all standard BlockNote block types. Produces output equivalent to
BlockNote's own ``blocksToMarkdownLossy()``.

Usage:
    from app.utils.blocknote_to_markdown import blocknote_to_markdown

    markdown = blocknote_to_markdown(blocknote_json)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline content → markdown text
# ---------------------------------------------------------------------------


def _render_inline_content(content: list[dict[str, Any]] | None) -> str:
    """Convert BlockNote inline content array to a markdown string."""
    if not content:
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type", "text")

        if item_type == "text":
            text = item.get("text", "")
            styles: dict[str, Any] = item.get("styles", {})

            # Apply inline styles (order: code first so nested marks don't break it)
            if styles.get("code"):
                text = f"`{text}`"
            else:
                if styles.get("bold"):
                    text = f"**{text}**"
                if styles.get("italic"):
                    text = f"*{text}*"
                if styles.get("strikethrough"):
                    text = f"~~{text}~~"
                # underline has no markdown equivalent — keep as plain text (lossy)

            parts.append(text)

        elif item_type == "link":
            href = item.get("href", "")
            link_content = item.get("content", [])
            link_text = _render_inline_content(link_content) if link_content else href
            parts.append(f"[{link_text}]({href})")

        else:
            # Unknown inline type — extract text if possible
            text = item.get("text", "")
            if text:
                parts.append(text)

    return "".join(parts)


# ---------------------------------------------------------------------------
# Block → markdown lines
# ---------------------------------------------------------------------------


def _render_block(
    block: dict[str, Any], indent: int = 0, numbered_list_counter: int = 0
) -> tuple[list[str], int]:
    """Convert a single BlockNote block (and its children) to markdown lines.

    Args:
        block: A BlockNote block dict.
        indent: Current indentation level (for nested children).
        numbered_list_counter: Current counter for consecutive numbered list items.

    Returns:
        A tuple of (list of markdown lines without trailing newlines,
        updated numbered_list_counter).
    """
    block_type = block.get("type", "paragraph")
    props: dict[str, Any] = block.get("props", {})
    content = block.get("content")
    children: list[dict[str, Any]] = block.get("children", [])
    prefix = "  " * indent  # 2-space indent per nesting level

    lines: list[str] = []

    # --- Block type handlers ---

    if block_type == "paragraph":
        text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}{text}")

    elif block_type == "heading":
        level = props.get("level", 1)
        hashes = "#" * min(max(level, 1), 6)
        text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}{hashes} {text}")

    elif block_type == "bulletListItem":
        text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}- {text}")

    elif block_type == "numberedListItem":
        # Use props.start if present, otherwise increment counter
        start = props.get("start")
        if start is not None:
            numbered_list_counter = int(start)
        else:
            numbered_list_counter += 1
        text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}{numbered_list_counter}. {text}")

    elif block_type == "checkListItem":
        checked = props.get("checked", False)
        marker = "[x]" if checked else "[ ]"
        text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}- {marker} {text}")

    elif block_type == "codeBlock":
        language = props.get("language", "")
        # Code blocks store content as a single text item
        code_text = _render_inline_content(content) if content else ""
        lines.append(f"{prefix}```{language}")
        for code_line in code_text.split("\n"):
            lines.append(f"{prefix}{code_line}")
        lines.append(f"{prefix}```")

    elif block_type == "table":
        # Table content is a nested structure: content.rows[].cells[][]
        table_content = block.get("content", {})
        rows: list[dict[str, Any]] = []

        if isinstance(table_content, dict):
            rows = table_content.get("rows", [])
        elif isinstance(table_content, list):
            # Some versions store rows directly as a list
            rows = table_content

        if rows:
            for row_idx, row in enumerate(rows):
                cells = row.get("cells", []) if isinstance(row, dict) else row
                cell_texts: list[str] = []
                for cell in cells:
                    if isinstance(cell, list):
                        # Cell is a list of inline content
                        cell_texts.append(_render_inline_content(cell))
                    elif isinstance(cell, dict):
                        # Cell is a tableCell object with its own content
                        cell_content = cell.get("content")
                        if isinstance(cell_content, list):
                            cell_texts.append(_render_inline_content(cell_content))
                        else:
                            cell_texts.append("")
                    elif isinstance(cell, str):
                        cell_texts.append(cell)
                    else:
                        cell_texts.append(str(cell))
                lines.append(f"{prefix}| {' | '.join(cell_texts)} |")
                # Add header separator after first row
                if row_idx == 0:
                    lines.append(f"{prefix}| {' | '.join('---' for _ in cell_texts)} |")

    elif block_type == "image":
        url = props.get("url", "")
        caption = props.get("caption", "") or props.get("name", "")
        if url:
            lines.append(f"{prefix}![{caption}]({url})")

    elif block_type == "video":
        url = props.get("url", "")
        caption = props.get("caption", "") or "video"
        if url:
            lines.append(f"{prefix}[{caption}]({url})")

    elif block_type == "audio":
        url = props.get("url", "")
        caption = props.get("caption", "") or "audio"
        if url:
            lines.append(f"{prefix}[{caption}]({url})")

    elif block_type == "file":
        url = props.get("url", "")
        name = props.get("name", "") or props.get("caption", "") or "file"
        if url:
            lines.append(f"{prefix}[{name}]({url})")

    else:
        # Unknown block type — extract text content if possible, skip otherwise
        if content:
            text = _render_inline_content(content) if isinstance(content, list) else ""
            if text:
                lines.append(f"{prefix}{text}")
        # If no content at all, silently skip (lossy)

    # --- Render nested children (indented) ---
    if children:
        for child in children:
            child_lines, numbered_list_counter = _render_block(
                child, indent=indent + 1, numbered_list_counter=numbered_list_counter
            )
            lines.extend(child_lines)

    return lines, numbered_list_counter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def blocknote_to_markdown(
    blocks: list[dict[str, Any]] | dict[str, Any] | None,
) -> str | None:
    """Convert a BlockNote document (list of blocks) to a markdown string.

    Args:
        blocks: BlockNote JSON — either a list of block dicts, or a single
                block dict, or None.

    Returns:
        Markdown string, or None if input is empty / unconvertible.

    Examples:
        >>> blocknote_to_markdown([
        ...     {"type": "heading", "props": {"level": 2},
        ...      "content": [{"type": "text", "text": "Hello", "styles": {}}],
        ...      "children": []},
        ...     {"type": "paragraph",
        ...      "content": [{"type": "text", "text": "World", "styles": {"bold": True}}],
        ...      "children": []},
        ... ])
        '## Hello\\n\\nWorld'
    """
    if not blocks:
        return None

    # Normalise: accept a single block as well as a list
    if isinstance(blocks, dict):
        blocks = [blocks]

    if not isinstance(blocks, list):
        logger.warning(
            f"blocknote_to_markdown received unexpected type: {type(blocks)}"
        )
        return None

    all_lines: list[str] = []
    prev_type: str | None = None
    numbered_list_counter: int = 0

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "paragraph")

        # Reset numbered list counter when we leave a numbered list run
        if block_type != "numberedListItem" and prev_type == "numberedListItem":
            numbered_list_counter = 0

        block_lines, numbered_list_counter = _render_block(
            block, numbered_list_counter=numbered_list_counter
        )

        # Add a blank line between blocks (standard markdown spacing)
        # Exception: consecutive list items of the same type don't get extra blank lines
        if all_lines and block_lines:
            same_list = block_type == prev_type and block_type in (
                "bulletListItem",
                "numberedListItem",
                "checkListItem",
            )
            if not same_list:
                all_lines.append("")

        all_lines.extend(block_lines)
        prev_type = block_type

    result = "\n".join(all_lines).strip()
    return result if result else None
