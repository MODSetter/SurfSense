"""Icons beside the registry: drawn by strangers and shown in the app, so small and inert."""

import re
import struct
from pathlib import Path
from typing import Any

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

ICON_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*\.(svg|png)$")
LARGEST_BYTES = 32 * 1024
SMALLEST_PNG_SIDE = 64
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Elements that run code or pull in other documents.
UNSAFE_ELEMENTS = {"script", "foreignobject", "iframe", "embed", "object"}
EXTERNAL_URL = re.compile(r"url\(\s*['\"]?\s*(https?:|//)|@import", re.IGNORECASE)


def icon_problems(plugins: list[Any], icons_dir: Path) -> list[str]:
    problems = []
    used: set[str] = set()
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict) or entry.get("icon") is None:
            continue
        name = entry["icon"]
        label = f'plugins[{index}] "{entry.get("id")}": icon'
        problem = _file_problem(name, icons_dir)
        if problem:
            problems.append(f"{label}: {problem}")
        if isinstance(name, str):
            used.add(name)
    if icons_dir.is_dir():
        problems += [
            f"icons/{path.name}: no entry uses it"
            for path in sorted(icons_dir.iterdir())
            if path.name not in used
        ]
    return problems


def _file_problem(name: Any, icons_dir: Path) -> str | None:
    if not (isinstance(name, str) and ICON_NAME.match(name)):
        return "must be a file name in icons/ ending in .svg or .png"
    path = icons_dir / name
    if not path.is_file():
        return f"icons/{name} does not exist"
    content = path.read_bytes()
    if len(content) > LARGEST_BYTES:
        return f"icons/{name} is larger than 32 KB"
    if name.endswith(".png"):
        return _png_problem(content)
    return _svg_problem(content)


def _png_problem(content: bytes) -> str | None:
    if not content.startswith(PNG_SIGNATURE) or content[12:16] != b"IHDR":
        return "is not a PNG"
    width, height = struct.unpack(">II", content[16:24])
    if width != height:
        return f"must be square, is {width}x{height}"
    if width < SMALLEST_PNG_SIDE:
        return f"must be at least 64x64, is {width}x{height}"
    return None


def _svg_problem(content: bytes) -> str | None:
    try:
        root = fromstring(content, forbid_dtd=True)
    except (DefusedXmlException, SyntaxError) as error:
        return f"is not a plain SVG: {error}"
    if _local(root.tag) != "svg":
        return "is not an SVG"
    for element in root.iter():
        tag = _local(element.tag)
        if tag in UNSAFE_ELEMENTS:
            return f"must not contain <{tag}>"
        for attribute, value in element.attrib.items():
            name = _local(attribute)
            if name.startswith("on"):
                return f"must not carry event attributes ({name})"
            if name in {"href", "src"} and not value.strip().startswith("#"):
                return f"must not reference anything outside itself ({value})"
            if EXTERNAL_URL.search(value):
                return f"must not reference anything outside itself ({value})"
        if element.text and EXTERNAL_URL.search(element.text):
            return "must not reference anything outside itself"
    return _square_problem(root.get("viewBox"))


def _square_problem(view_box: str | None) -> str | None:
    try:
        _, _, width, height = (
            float(n) for n in (view_box or "").replace(",", " ").split()
        )
    except ValueError:
        return "needs a viewBox"
    if width <= 0 or width != height:
        return f"must be square, viewBox is {view_box}"
    return None


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()
