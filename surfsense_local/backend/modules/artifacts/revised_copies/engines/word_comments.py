"""Real Word comments: the comments part, a comment's range in the text, and removing them."""

import posixpath
from collections.abc import Collection

from lxml import etree

from modules.artifacts.revised_copies.engines.package import Package
from modules.artifacts.revised_copies.engines.word_tracking import Stamp, new_run
from modules.artifacts.revised_copies.engines.word_xml import (
    COMMENT_END,
    COMMENT_REF,
    COMMENT_START,
    COMMENTS_EXTENDED_REL,
    COMMENTS_EXTENSIBLE_REL,
    COMMENTS_IDS_REL,
    COMMENTS_REL,
    COMMENTS_TYPE,
    RPR,
    P,
    R,
    W,
    make,
    w,
)

_METADATA_RELS = (COMMENTS_EXTENDED_REL, COMMENTS_IDS_REL, COMMENTS_EXTENSIBLE_REL)


def _initials(author: str) -> str:
    capitals = "".join(c for c in author if c.isupper())
    return (capitals or author[:1] or "S")[:9]


class Comments:
    """The comments part in memory, created on the first comment and written back on save."""

    def __init__(self, package: Package, main_part: str) -> None:
        names = package.related(main_part, COMMENTS_REL)
        self._name = names[0] if names else None
        self.root = package.xml(self._name) if self._name else None
        self._changed = False

    def add(self, text: str, stamp: Stamp) -> str:
        if self.root is None:
            self.root = etree.Element(w("comments"), nsmap={"w": W})
        comment_id = stamp.new_id()
        comment = make(
            "comment",
            id=comment_id,
            author=stamp.author,
            date=stamp.date,
            initials=_initials(stamp.author),
        )
        for index, line in enumerate(text.split("\n")):
            paragraph = etree.SubElement(comment, P)
            if index == 0:
                reference = etree.SubElement(paragraph, R)
                etree.SubElement(reference, w("annotationRef"))
            if line:
                paragraph.append(new_run(line, None))
        self.root.append(comment)
        self._changed = True
        return comment_id

    def save(self, package: Package, main_part: str) -> None:
        if not self._changed or self.root is None:
            return
        if self._name is not None:
            package.set_xml(self._name, self.root)
            return
        folder = posixpath.dirname(main_part)
        name = posixpath.join(folder, "comments.xml")
        number = 1
        while name in package.names:
            name = posixpath.join(folder, f"comments{number}.xml")
            number += 1
        package.add_part(name, self.root, COMMENTS_TYPE, main_part, COMMENTS_REL)
        self._name = name


def range_start(comment_id: str) -> etree._Element:
    return make("commentRangeStart", id=comment_id)


def range_end(comment_id: str) -> etree._Element:
    return make("commentRangeEnd", id=comment_id)


def reference_run(comment_id: str) -> etree._Element:
    run = etree.Element(R)
    run.append(make("commentReference", id=comment_id))
    return run


def strip_anchors(root: etree._Element, ids: Collection[str] | None) -> bool:
    """Remove the ranges and references of these comments (all when None); True if any."""
    removed = False
    for element in list(root.iter(COMMENT_START, COMMENT_END, COMMENT_REF)):
        if ids is not None and element.get(w("id")) not in ids:
            continue
        parent = element.getparent()
        parent.remove(element)
        removed = True
        if parent.tag == R and all(child.tag == RPR for child in parent):
            parent.getparent().remove(parent)
    return removed


def _local(name: str) -> str:
    return etree.QName(name).localname


def remove_comments(
    package: Package, main_part: str, ids: Collection[str]
) -> list[str]:
    """Drop these comments from the comments part and its metadata parts; returns changed parts."""
    names = package.related(main_part, COMMENTS_REL)
    if not names:
        return []
    root = package.xml(names[0])
    para_ids: set[str] = set()
    for comment in list(root.iter(w("comment"))):
        if comment.get(w("id")) in ids:
            para_ids.update(
                value
                for paragraph in comment.iter(P)
                for key, value in paragraph.attrib.items()
                if _local(key) == "paraId"
            )
            root.remove(comment)
    package.set_xml(names[0], root)
    changed = [names[0]]
    durable_ids: set[str] = set()
    for rel in _METADATA_RELS:
        for name in package.related(main_part, rel):
            part = package.xml(name)
            dropped = False
            for item in list(part):
                values = {_local(k): v for k, v in item.attrib.items()}
                if (
                    values.get("paraId") in para_ids
                    or values.get("durableId") in durable_ids
                ):
                    if "durableId" in values:
                        durable_ids.add(values["durableId"])
                    part.remove(item)
                    dropped = True
            if dropped:
                package.set_xml(name, part)
                changed.append(name)
    return changed


def remove_all_comment_parts(package: Package, main_part: str) -> None:
    for rel in (COMMENTS_REL, *_METADATA_RELS):
        for name in package.related(main_part, rel):
            package.remove(name)
