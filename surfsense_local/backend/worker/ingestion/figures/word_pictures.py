"""What a Word file holds where Docling looks for pictures: the body, the headers
and the footers. Read from the package's relationships and markup, without Docling."""

import posixpath
import zipfile
from collections.abc import Collection
from enum import Enum
from pathlib import Path

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree

_RELATIONSHIP = (
    "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
)
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)
_HEADERS_AND_FOOTERS = frozenset({RT.HEADER, RT.FOOTER})
# A w:drawing tag under any prefix. Text that merely says ":drawing" costs one
# Docling read at most.
_DRAWING_TAGS = (b":drawing", b"<drawing")


class WordPictures(Enum):
    NONE = "none"  # Docling would find no picture
    EMBEDDED = "embedded"  # an image the file carries
    DRAWN = "drawn"  # shapes only, which Docling draws when LibreOffice is on PATH


def pictures_in_word_file(original: Path) -> WordPictures:
    """EMBEDDED also when the package cannot be read that far: Docling then decides."""
    try:
        with zipfile.ZipFile(original) as package:
            parts = [
                part
                for main in _related(package, "", {RT.OFFICE_DOCUMENT})
                for part in (main, *_related(package, main, _HEADERS_AND_FOOTERS))
            ]
            if any(_related(package, part, {RT.IMAGE}) for part in parts):
                return WordPictures.EMBEDDED
            if any(_draws(package, part) for part in parts):
                return WordPictures.DRAWN
    except Exception:  # a damaged package: one more Docling read at most
        return WordPictures.EMBEDDED
    return WordPictures.NONE


def _draws(package: zipfile.ZipFile, part: str) -> bool:
    try:
        xml = package.read(part)
    except KeyError:
        return False
    return any(tag in xml for tag in _DRAWING_TAGS)


def _related(package: zipfile.ZipFile, part: str, types: Collection[str]) -> list[str]:
    """The parts inside the package this one relates to by those types, by zip name."""
    folder, name = posixpath.split(part)
    try:
        xml = package.read(posixpath.join(folder, "_rels", f"{name}.rels"))
    except KeyError:
        return []
    found = []
    for relationship in etree.fromstring(xml, _PARSER).iterchildren(_RELATIONSHIP):
        if relationship.get("Type") not in types:
            continue
        if relationship.get("TargetMode") == "External":
            continue  # Docling keeps only the pixels a file carries
        target = relationship.get("Target", "")
        found.append(
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join(folder, target))
        )
    return found
