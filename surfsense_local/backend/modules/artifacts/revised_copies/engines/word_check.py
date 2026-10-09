"""Word-specific faults the engine must never add: repeated revision ids, orphan comment marks."""

from collections import Counter

from modules.artifacts.revised_copies.engines.package import Package
from modules.artifacts.revised_copies.engines.word_xml import (
    COMMENT_END,
    COMMENT_REF,
    COMMENT_START,
    COMMENTS_REL,
    DEL,
    DEL_TEXT,
    INS,
    MOVE_FROM,
    MOVE_TO,
    STORY_RELS,
    T,
    w,
)

TEXT_BOX = w("txbxContent")


def stories(package: Package, main_part: str) -> list[str]:
    """The main document and the parts with their own text: headers, footers, notes, comments."""
    found = [main_part]
    for rel in STORY_RELS:
        found.extend(n for n in package.related(main_part, rel) if n in package.names)
    return list(dict.fromkeys(found))


def _deleted(node) -> bool:
    """Inside a deletion of its own story; a text box inside a deleted run is its own story."""
    for ancestor in node.iterancestors():
        if ancestor.tag == TEXT_BOX:
            return False
        if ancestor.tag in (DEL, MOVE_FROM):
            return True
    return False


def word_problems(package: Package, main_part: str) -> list[str]:
    problems: list[str] = []
    revision_ids: Counter[str] = Counter()
    anchors: list[tuple[str, str]] = []
    for name in stories(package, main_part):
        root = package.xml(name)
        for element in root.iter(INS, DEL, MOVE_FROM, MOVE_TO):
            revision_ids[element.get(w("id"), "")] += 1
        for element in root.iter(T):
            if _deleted(element):
                problems.append(f"{name}: text inside a deletion is not w:delText")
                break
        for element in root.iter(DEL_TEXT):
            if not any(a.tag in (DEL, MOVE_FROM) for a in element.iterancestors()):
                problems.append(f"{name}: w:delText outside a deletion")
                break
        anchors.extend(
            (name, element.get(w("id"), ""))
            for element in root.iter(COMMENT_START, COMMENT_END, COMMENT_REF)
        )
    problems.extend(
        f"revision id {i} repeats" for i, n in revision_ids.items() if n > 1
    )
    comment_ids: Counter[str] = Counter()
    for name in package.related(main_part, COMMENTS_REL):
        if name in package.names:
            comment_ids.update(
                c.get(w("id"), "") for c in package.xml(name).iter(w("comment"))
            )
    problems.extend(f"comment id {i} repeats" for i, n in comment_ids.items() if n > 1)
    problems.extend(
        f"{name}: comment mark {i} has no comment"
        for name, i in anchors
        if i not in comment_ids
    )
    return problems
