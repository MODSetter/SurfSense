"""Structural checks over PPTX OOXML bytes."""

from __future__ import annotations

import posixpath
from xml.etree import ElementTree
from zipfile import ZipFile

from .base import StructuralCheckResult
from .ooxml import OoxmlError, open_ooxml

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
P = f"{{{P_NS}}}"
A = f"{{{A_NS}}}"
R = f"{{{R_NS}}}"
REL = f"{{{REL_NS}}}"

PRESENTATION_PART = "ppt/presentation.xml"
PRESENTATION_RELS_PART = "ppt/_rels/presentation.xml.rels"
REQUIRED_PARTS = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        PRESENTATION_PART,
        PRESENTATION_RELS_PART,
    }
)
MAX_XML_PART_BYTES = 10 * 1024 * 1024
DRAWABLE_SHAPES = frozenset(
    {"sp", "pic", "graphicFrame", "cxnSp", "grpSp", "contentPart"}
)


def _part_target(source_part: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _relationships(
    archive: ZipFile, rels_part: str, *, source_part: str
) -> dict[str, tuple[str, str, bool]]:
    if rels_part not in archive.namelist():
        return {}
    if archive.getinfo(rels_part).file_size > MAX_XML_PART_BYTES:
        raise OoxmlError(f"PPTX {rels_part} exceeds {MAX_XML_PART_BYTES} bytes")
    root = ElementTree.fromstring(archive.read(rels_part))
    relationships: dict[str, tuple[str, str, bool]] = {}
    for relationship in root.findall(f"{REL}Relationship"):
        rel_id = relationship.get("Id")
        target = relationship.get("Target")
        if not rel_id or not target:
            continue
        relationships[rel_id] = (
            _part_target(source_part, target),
            relationship.get("Type", ""),
            relationship.get("TargetMode") == "External",
        )
    return relationships


def _integer(element: ElementTree.Element, attribute: str) -> int | None:
    raw = element.get(attribute)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _check_shape_geometry(
    shape: ElementTree.Element,
    *,
    shape_kind: str,
    slide_number: int,
    slide_width: int,
    slide_height: int,
    findings: list[str],
) -> None:
    xfrm = shape.find(f".//{A}xfrm")
    if xfrm is None:
        xfrm = shape.find(f".//{P}xfrm")
    if xfrm is None:
        return
    offset = xfrm.find(f"{A}off")
    extent = xfrm.find(f"{A}ext")
    if offset is None or extent is None:
        return
    x = _integer(offset, "x")
    y = _integer(offset, "y")
    width = _integer(extent, "cx")
    height = _integer(extent, "cy")
    if None in {x, y, width, height}:
        findings.append(f"slide {slide_number} has invalid shape geometry")
        return
    assert x is not None and y is not None and width is not None and height is not None
    invalid_extent = (
        width < 0
        or height < 0
        or (width == 0 and height == 0)
        or (shape_kind != "cxnSp" and (width == 0 or height == 0))
    )
    if invalid_extent:
        findings.append(f"slide {slide_number} has a shape with non-positive extent")
        return
    # ponytail: only wholly off-canvas shapes block; partial bleed is intentional
    # in many decks, and shapes touching the canvas boundary remain visible.
    if x > slide_width or y > slide_height or x + width < 0 or y + height < 0:
        findings.append(f"slide {slide_number} has a shape entirely off the canvas")


def _check_slide(
    archive: ZipFile,
    slide_part: str,
    *,
    slide_number: int,
    slide_width: int,
    slide_height: int,
    findings: list[str],
) -> None:
    if archive.getinfo(slide_part).file_size > MAX_XML_PART_BYTES:
        raise OoxmlError(f"PPTX {slide_part} exceeds {MAX_XML_PART_BYTES} bytes")
    slide = ElementTree.fromstring(archive.read(slide_part))
    if slide.get("show") == "0":
        findings.append(
            f"slide {slide_number} is hidden; delete it so every delivered slide "
            "is rendered and verified"
        )

    shape_tree = slide.find(f"{P}cSld/{P}spTree")
    shapes = (
        [
            child
            for child in shape_tree
            if child.tag.rsplit("}", 1)[-1] in DRAWABLE_SHAPES
        ]
        if shape_tree is not None
        else []
    )
    if not shapes:
        findings.append(f"slide {slide_number} contains no drawable shapes")
    for shape in shapes:
        _check_shape_geometry(
            shape,
            shape_kind=shape.tag.rsplit("}", 1)[-1],
            slide_number=slide_number,
            slide_width=slide_width,
            slide_height=slide_height,
            findings=findings,
        )

    for crop in slide.iter(f"{A}srcRect"):
        values = {
            side: _integer(crop, side) if crop.get(side) is not None else 0
            for side in ("l", "t", "r", "b")
        }
        if any(value is None for value in values.values()):
            findings.append(f"slide {slide_number} has an invalid picture crop")
        elif (
            values["l"] + values["r"] >= 100_000 or values["t"] + values["b"] >= 100_000
        ):
            findings.append(
                f"slide {slide_number} has a picture crop that removes the entire image"
            )

    rels_part = (
        f"{posixpath.dirname(slide_part)}/_rels/{posixpath.basename(slide_part)}.rels"
    )
    relationships = _relationships(archive, rels_part, source_part=slide_part)
    for blip in slide.iter(f"{A}blip"):
        rel_id = blip.get(f"{R}embed")
        if rel_id is None:
            continue
        relationship = relationships.get(rel_id)
        if (
            relationship is None
            or relationship[2]
            or not relationship[1].endswith("/image")
            or relationship[0] not in archive.namelist()
        ):
            findings.append(f"slide {slide_number} references missing embedded media")


def check_pptx(data: bytes) -> StructuralCheckResult:
    """Check a presentation package without attempting rendered text layout."""
    if not data:
        return StructuralCheckResult(("PPTX is empty",), page_count=0)

    findings: list[str] = []
    page_count = 0
    try:
        with open_ooxml(
            data,
            format_name="PPTX",
            required_parts=REQUIRED_PARTS,
            part_limits={
                PRESENTATION_PART: MAX_XML_PART_BYTES,
                PRESENTATION_RELS_PART: MAX_XML_PART_BYTES,
            },
        ) as archive:
            presentation = ElementTree.fromstring(archive.read(PRESENTATION_PART))
            slide_size = presentation.find(f"{P}sldSz")
            slide_width = _integer(slide_size, "cx") if slide_size is not None else None
            slide_height = (
                _integer(slide_size, "cy") if slide_size is not None else None
            )
            if (
                slide_width is None
                or slide_height is None
                or slide_width <= 0
                or slide_height <= 0
            ):
                return StructuralCheckResult(
                    ("PPTX has no positive presentation-wide slide size",),
                    page_count=0,
                )

            slide_list = presentation.find(f"{P}sldIdLst")
            slide_ids = (
                list(slide_list.findall(f"{P}sldId")) if slide_list is not None else []
            )
            page_count = len(slide_ids)
            if not slide_ids:
                return StructuralCheckResult(("PPTX contains no slides",), page_count=0)

            relationships = _relationships(
                archive,
                PRESENTATION_RELS_PART,
                source_part=PRESENTATION_PART,
            )
            for slide_number, slide_id in enumerate(slide_ids, start=1):
                rel_id = slide_id.get(f"{R}id")
                relationship = relationships.get(rel_id or "")
                if (
                    relationship is None
                    or relationship[2]
                    or not relationship[1].endswith("/slide")
                    or relationship[0] not in archive.namelist()
                ):
                    findings.append(
                        f"slide {slide_number} points to a missing slide part"
                    )
                    continue
                _check_slide(
                    archive,
                    relationship[0],
                    slide_number=slide_number,
                    slide_width=slide_width,
                    slide_height=slide_height,
                    findings=findings,
                )
    except OoxmlError as exc:
        return StructuralCheckResult((str(exc),), page_count=page_count)
    except ElementTree.ParseError:
        return StructuralCheckResult(
            ("PPTX is not valid OOXML",), page_count=page_count
        )

    return StructuralCheckResult(tuple(findings), page_count=page_count)
