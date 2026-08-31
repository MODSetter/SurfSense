"""Programmatic checks for bounded Markdown-backed mind-map PNGs."""

from __future__ import annotations

import io
import re
import struct

from PIL import Image, ImageChops, UnidentifiedImageError

from .base import StructuralCheckResult

MINDMAP_WIDTH = 2400
MINDMAP_HEIGHT = 1600
MINDMAP_MAX_NODES = 60
MINDMAP_MAX_DEPTH = 6
MINDMAP_MAX_LABEL_CHARS = 120
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MIN_NON_BACKGROUND_PIXELS = 100
_ROOT_RE = re.compile(r"^#(?:[ \t]+)(.+?)$")
_LIST_RE = re.compile(r"^( *)([-+*])(?:[ \t]+)(.+?)$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNSAFE_RE = re.compile(
    r"(^|\s)(```|~~~|:::) |"
    r"!\[[^\]]*\](?:\(|\[)|"
    r"\[[^\]]+\](?:\(|\[)|"
    r"<[^>\n]+>",
    re.IGNORECASE | re.VERBOSE,
)


def check_mindmap_markdown(data: bytes) -> StructuralCheckResult:
    """Validate the intentionally small Markdown hierarchy accepted by Markmap."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return StructuralCheckResult(("Mind-map Markdown must be valid UTF-8",))

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if _CONTROL_RE.search(text):
        return StructuralCheckResult(
            ("Mind-map Markdown contains unsupported control characters",)
        )
    if _UNSAFE_RE.search(text):
        return StructuralCheckResult(
            ("Mind-map Markdown contains an unsafe or unsupported construct",)
        )

    lines = [
        (number, line)
        for number, line in enumerate(text.split("\n"), 1)
        if line.strip()
    ]
    if not lines:
        return StructuralCheckResult(("Mind-map Markdown needs one non-empty H1 root",))

    root_line, root = lines[0]
    root_match = _ROOT_RE.fullmatch(root)
    if root_match is None or not root_match.group(1).strip():
        return StructuralCheckResult(
            (f"Line {root_line} must be the single non-empty H1 root",)
        )
    root_label = root_match.group(1).strip()
    if len(root_label) > MINDMAP_MAX_LABEL_CHARS:
        return StructuralCheckResult(
            (f"Root label exceeds {MINDMAP_MAX_LABEL_CHARS} characters; shorten it",)
        )

    findings: list[str] = []
    indent_width: int | None = None
    previous_level = 0
    node_count = 1
    max_depth = 1
    for index, (line_number, line) in enumerate(lines[1:]):
        if line.lstrip().startswith("#"):
            findings.append("Mind-map Markdown must contain exactly one heading")
            break
        match = _LIST_RE.fullmatch(line)
        if match is None:
            findings.append(
                f"Line {line_number} must be a non-empty unordered-list node"
            )
            break
        indent = len(match.group(1))
        if index == 0 and indent:
            findings.append(f"Line {line_number} must start at the first list level")
            break
        label = match.group(3).strip()
        if not label:
            findings.append(f"Line {line_number} has an empty node label")
            break
        if len(label) > MINDMAP_MAX_LABEL_CHARS:
            findings.append(
                f"Line {line_number} label exceeds "
                f"{MINDMAP_MAX_LABEL_CHARS} characters; shorten it"
            )
            break

        if indent:
            if indent_width is None:
                indent_width = indent
                if not 2 <= indent_width <= 4:
                    findings.append(
                        f"Line {line_number} skips a nesting level; use 2-4 spaces"
                    )
                    break
            if indent % indent_width:
                findings.append(
                    f"Line {line_number} skips or inconsistently indents a level"
                )
                break
            level = indent // indent_width
        else:
            level = 0
        if level > previous_level + 1:
            findings.append(f"Line {line_number} skips a nesting level")
            break
        previous_level = level

        depth = level + 2
        node_count += 1
        max_depth = max(max_depth, depth)
        if depth > MINDMAP_MAX_DEPTH:
            findings.append(
                f"Mind map exceeds depth {MINDMAP_MAX_DEPTH}; split or simplify it"
            )
            break
        if node_count > MINDMAP_MAX_NODES:
            findings.append(
                f"Mind map exceeds {MINDMAP_MAX_NODES} nodes; split or simplify it"
            )
            break

    if not findings and node_count == 1:
        findings.append("Mind-map root needs at least one child node")
    return StructuralCheckResult(
        tuple(findings),
        notes=(f"Mind-map hierarchy: {node_count} nodes, depth {max_depth}",)
        if not findings
        else (),
    )


def _png_ends_at_iend(data: bytes) -> bool:
    offset = len(_PNG_SIGNATURE)
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            return False
        chunk_type = data[offset + 4 : offset + 8]
        offset = chunk_end
        if chunk_type == b"IEND":
            return offset == len(data) and length == 0
    return False


def check_mindmap_png(data: bytes) -> StructuralCheckResult:
    """Fully decode and sanity-check a deterministic mind-map still."""
    if not data.startswith(_PNG_SIGNATURE) or not _png_ends_at_iend(data):
        return StructuralCheckResult(("Mind-map output must be one complete PNG",))

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.size != (MINDMAP_WIDTH, MINDMAP_HEIGHT):
                return StructuralCheckResult(
                    (
                        "Mind-map PNG must be exactly "
                        f"{MINDMAP_WIDTH}x{MINDMAP_HEIGHT} pixels",
                    )
                )
            if image.mode not in {"RGB", "RGBA"}:
                return StructuralCheckResult(
                    ("Mind-map PNG must use RGB or RGBA color",)
                )
            if image.mode == "RGBA":
                alpha = image.getchannel("A")
                if alpha.getextrema() != (255, 255):
                    return StructuralCheckResult(
                        ("Mind-map PNG must use a fully opaque canvas",)
                    )
                image = image.convert("RGB")
            extrema = image.getextrema()
            background = Image.new("RGB", image.size, image.getpixel((0, 0)))
            red, green, blue = ImageChops.difference(image, background).split()
            changed = ImageChops.lighter(ImageChops.lighter(red, green), blue)
            non_background_pixels = image.width * image.height - changed.histogram()[0]
    except (OSError, UnidentifiedImageError, ValueError):
        return StructuralCheckResult(("Mind-map PNG is corrupt or truncated",))

    if all(low == high for low, high in extrema):
        return StructuralCheckResult(("Mind-map PNG must not be a single color",))
    if non_background_pixels < _MIN_NON_BACKGROUND_PIXELS:
        return StructuralCheckResult(("Mind-map PNG is effectively blank",))
    return StructuralCheckResult(
        (),
        notes=(f"Mind-map PNG: {MINDMAP_WIDTH}x{MINDMAP_HEIGHT}",),
    )
