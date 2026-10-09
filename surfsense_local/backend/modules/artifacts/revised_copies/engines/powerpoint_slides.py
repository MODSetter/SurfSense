"""The deck's slide list (ECMA-376 Part 1, 19.2.1.34 sldIdLst): finding a slide
by its number as sent, deleting one and duplicating one with valid relationships."""

from __future__ import annotations

import posixpath
import re
from urllib.parse import unquote

from lxml import etree

from modules.artifacts.revised_copies.engines.package import (
    Package,
    PackageRefusedError,
    rels_name,
)

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PR = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_SLIDE_TYPE = f"{R}/slide"
_SECTION_SLIDE = "{http://schemas.microsoft.com/office/powerpoint/2010/main}sldId"
_LINKS = {"hlinkClick", "hlinkHover", "hlinkMouseOver"}
# Elements elsewhere that name a slide by r:id: links, and outline-view entries (viewProps).
_POINTERS = _LINKS | {"sld"}
# Parts a copied slide points at rather than owns.
_SHARED = {
    "slideLayout",
    "slideMaster",
    "notesMaster",
    "handoutMaster",
    "theme",
    "image",
    "media",
    "audio",
    "video",
    "hyperlink",
    "slide",
    "font",
}
# Comments belong to the slide they were made on; a copy starts without them.
_DROPPED = {"comments", "commentAuthors"}


class Deck:
    def __init__(self, package: Package):
        self.package = package
        main = next(
            (
                r
                for r in package.relationships("")
                if r.get("Type", "").endswith("/officeDocument")
            ),
            None,
        )
        part = _resolve("", main.get("Target", "")) if main is not None else ""
        kind = (package.content_type(part) or "") if part in package.names else ""
        if "presentationml" not in kind and "ms-powerpoint" not in kind:
            raise PackageRefusedError(
                "NOT_A_PRESENTATION",
                {},
                "The file has no presentation part, so it is not a PowerPoint deck.",
            )
        self.part = part
        self.root = package.xml(part)
        self._list = self.root.find(f"{{{P}}}sldIdLst")
        self._sent = list(self._list) if self._list is not None else []
        self._gone: set[int] = set()
        self._roots: dict[str, etree._Element] = {}

    @property
    def count(self) -> int:
        return len(self._sent)

    @property
    def remaining(self) -> int:
        return len(self._list) if self._list is not None else 0

    def is_deleted(self, number: int) -> bool:
        return number in self._gone

    def slide_part(self, number: int) -> str | None:
        if not 1 <= number <= self.count or number in self._gone:
            return None
        rid = self._sent[number - 1].get(f"{{{R}}}id")
        target = self._target(self.part, rid)
        return target if target in self.package.names else None

    def notes_part(self, slide_part: str) -> str | None:
        for rel in self.package.relationships(slide_part):
            if (
                rel.get("Type", "").endswith("/notesSlide")
                and rel.get("TargetMode") != "External"
            ):
                target = _resolve(slide_part, rel.get("Target", ""))
                if target in self.package.names:
                    return target
        return None

    def xml(self, part: str) -> etree._Element:
        if part not in self._roots:
            self._roots[part] = self.package.xml(part)
        return self._roots[part]

    def save_xml(self, part: str) -> None:
        self.package.set_xml(part, self._roots[part])

    # --- delete --------------------------------------------------------------

    def delete(self, number: int) -> None:
        element = self._sent[number - 1]
        part = self.slide_part(number)
        rid = element.get(f"{{{R}}}id")
        self._list.remove(element)
        for listed in self.root.iter(f"{{{P}}}sld"):
            if listed.get(f"{{{R}}}id") == rid:
                listed.getparent().remove(listed)
        for listed in self.root.iter(_SECTION_SLIDE):
            if listed.get("id") == element.get("id"):
                listed.getparent().remove(listed)
        self.package.set_xml(self.part, self.root)
        self._gone.add(number)
        if part is None:
            return
        owned = self._internal_targets(part)
        self._unlink(part)
        self._roots.pop(part, None)
        self.package.remove(part)
        self._collect(owned)

    def _unlink(self, part: str) -> None:
        """Links to a deleted slide go with it, so no r:id is left without its relationship."""
        for rels in [n for n in self.package.names if n.endswith(".rels")]:
            source = _rels_source(rels)
            if source in (part, self.part) or source not in self.package.names:
                continue
            ids = {
                rel.get("Id")
                for rel in self.package.xml(rels).iter(f"{{{_PR}}}Relationship")
                if rel.get("TargetMode") != "External"
                and _resolve(source, rel.get("Target", "")) == part
            }
            if not ids or not source.endswith(".xml"):
                continue
            root = self.xml(source)
            for element in list(root.iter(etree.Element)):
                if etree.QName(element).localname in _POINTERS and _references(
                    element, ids
                ):
                    element.getparent().remove(element)
            self.save_xml(source)

    def _collect(self, candidates: list[str]) -> None:
        """Parts only the deleted slide used (its notes, its pictures) go too."""
        queue = list(candidates)
        while queue:
            name = queue.pop(0)
            if name not in self.package.names or name in self._referenced():
                continue
            queue.extend(self._internal_targets(name))
            self._roots.pop(name, None)
            self.package.remove(name)

    def _referenced(self) -> set[str]:
        found = set()
        for rels in [n for n in self.package.names if n.endswith(".rels")]:
            source = _rels_source(rels)
            for rel in self.package.xml(rels).iter(f"{{{_PR}}}Relationship"):
                if rel.get("TargetMode") != "External":
                    found.add(_resolve(source, rel.get("Target", "")))
        return found

    def _internal_targets(self, part: str) -> list[str]:
        return [
            _resolve(part, rel.get("Target", ""))
            for rel in self.package.relationships(part)
            if rel.get("TargetMode") != "External"
        ]

    # --- duplicate -----------------------------------------------------------

    def duplicate(self, number: int) -> None:
        element = self._sent[number - 1]
        source = self.slide_part(number)
        copies: dict[str, str] = {}
        copy_name = self._copy(source, copies)

        rels_part = rels_name(self.part)
        rels = self.package.xml(rels_part)
        taken = {rel.get("Id") for rel in rels}
        index = len(taken) + 1
        while f"rId{index}" in taken:
            index += 1
        rid = f"rId{index}"
        rel = etree.SubElement(rels, f"{{{_PR}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", _SLIDE_TYPE)
        rel.set(
            "Target", posixpath.relpath(copy_name, posixpath.dirname(self.part) or ".")
        )
        self.package.set_xml(rels_part, rels)

        new_id = str(max(int(e.get("id", "255")) for e in self._list) + 1)
        added = etree.Element(f"{{{P}}}sldId")
        added.set("id", new_id)
        added.set(f"{{{R}}}id", rid)
        element.addnext(added)
        for listed in list(self.root.iter(_SECTION_SLIDE)):
            if listed.get("id") == element.get("id"):
                section_copy = etree.Element(_SECTION_SLIDE)
                section_copy.set("id", new_id)
                listed.addnext(section_copy)
        self.package.set_xml(self.part, self.root)

    def _copy(self, part: str, copies: dict[str, str]) -> str:
        """Copies a part and what it owns; shared parts keep one copy."""
        name = self._free_name(part)
        copies[part] = name
        self.package.set_bytes(name, self.package.read(part))
        self._type_like(name, part)

        dropped: set[str] = set()
        rels = self.package.relationships(part)
        if not rels:
            return name
        new_rels = etree.Element(f"{{{_PR}}}Relationships", nsmap={None: _PR})
        for rel in rels:
            kind = rel.get("Type", "").rsplit("/", 1)[-1]
            if kind in _DROPPED:
                dropped.add(rel.get("Id"))
                continue
            copied = etree.SubElement(
                new_rels, f"{{{_PR}}}Relationship", dict(rel.attrib)
            )
            if rel.get("TargetMode") == "External":
                continue
            target = _resolve(part, rel.get("Target", ""))
            if target in copies:
                target = copies[target]
            elif kind not in _SHARED and target in self.package.names:
                target = self._copy(target, copies)
            copied.set(
                "Target", posixpath.relpath(target, posixpath.dirname(name) or ".")
            )
        self.package.set_xml(rels_name(name), new_rels)
        if dropped:
            root = self.package.xml(name)
            for element in list(root.iter(etree.Element)):
                if _references(element, dropped) and element.getparent() is not None:
                    element.getparent().remove(element)
            self.package.set_xml(name, root)
        return name

    def _free_name(self, part: str) -> str:
        folder, base = posixpath.split(part)
        stem, _, extension = re.fullmatch(r"(.*?)(\d*)(\.[^.]*)?", base).groups()
        extension = extension or ""
        lowered = {n.lower() for n in self.package.names}
        number = 1
        while posixpath.join(folder, f"{stem}{number}{extension}").lower() in lowered:
            number += 1
        return posixpath.join(folder, f"{stem}{number}{extension}")

    def _type_like(self, name: str, original: str) -> None:
        kind = self.package.content_type(original)
        types = self.package.xml("[Content_Types].xml")
        overridden = any(
            o.get("PartName", "").lstrip("/").lower() == original.lower()
            for o in types.iter(f"{{{_CT}}}Override")
        )
        if kind and overridden:
            override = etree.SubElement(types, f"{{{_CT}}}Override")
            override.set("PartName", f"/{name}")
            override.set("ContentType", kind)
            self.package.set_xml("[Content_Types].xml", types)

    def _target(self, source: str, rid: str | None) -> str | None:
        for rel in self.package.relationships(source):
            if rel.get("Id") == rid and rel.get("TargetMode") != "External":
                return _resolve(source, rel.get("Target", ""))
        return None


def _resolve(source: str, target: str) -> str:
    target = unquote(target.split("#", 1)[0])
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _rels_source(rels: str) -> str:
    folder, file = posixpath.split(rels)
    return posixpath.join(posixpath.dirname(folder), file.removesuffix(".rels"))


def _references(element: etree._Element, ids: set[str]) -> bool:
    return any(k.startswith(f"{{{R}}}") and v in ids for k, v in element.attrib.items())
