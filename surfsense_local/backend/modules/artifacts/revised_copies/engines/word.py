"""The Word engine: a revised copy of a .docx whose every edit is a tracked change.

The user's file is only read. Edits land in `out` as w:ins and w:del by one
author and date, comments as real comments; there is no untracked path.
Accepting all, rejecting all and the external copy work on any author's markup.
"""

import hashlib
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.artifacts.revised_copies.engines.package import (
    Package,
    PackageRefusedError,
    open_package,
    package_problems,
)
from modules.artifacts.revised_copies.engines.report import (
    Notice,
    Report,
    nothing_changed,
    skip_others,
)
from modules.artifacts.revised_copies.engines.word_check import stories, word_problems
from modules.artifacts.revised_copies.engines.word_comments import (
    Comments,
    remove_all_comment_parts,
    remove_comments,
    strip_anchors,
)
from modules.artifacts.revised_copies.engines.word_decide import Decision, decide_all
from modules.artifacts.revised_copies.engines.word_ops import (
    EditedDocument,
    run_operation,
)
from modules.artifacts.revised_copies.engines.word_tracking import Stamp
from modules.artifacts.revised_copies.engines.word_xml import (
    COMMENTS_REL,
    DEL,
    INS,
    MOVE_FROM,
    MOVE_TO,
    OFFICE_DOCUMENT_REL,
    w,
)


@dataclass(frozen=True)
class RevisionCounts:
    changes: int
    comments: int


def main_part(package: Package) -> str:
    """The document part the package's officeDocument relationship names."""
    names = package.related("", OFFICE_DOCUMENT_REL)
    if names and names[0] in package.names:
        root = package.xml(names[0])
        if root.tag == w("document") and root.find(w("body")) is not None:
            return names[0]
    raise PackageRefusedError(
        "NOT_A_WORD_DOCUMENT", {}, "The file is not a Word document SurfSense can read."
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _next_id(package: Package, main: str) -> int:
    """One past every numeric w:id in the text parts, so new ids clash with none."""
    highest = 0
    attribute = w("id")
    for name in stories(package, main):
        for element in package.xml(name).iter():
            value = element.get(attribute) if isinstance(element.tag, str) else None
            if value is not None and value.lstrip("-").isdigit():
                highest = max(highest, int(value))
    return highest + 1


def _problems(package: Package, main: str) -> set[str]:
    return set(package_problems(package)) | set(word_problems(package, main))


def apply(
    original: Path,
    operations: list[dict[str, Any]],
    out: Path,
    *,
    partial: bool = False,
    author: str = "SurfSense",
    date: datetime | None = None,
) -> Report:
    """Run the operations in order on a copy of `original`, saved to `out` only if all hold."""
    data = original.read_bytes()
    input_sha = _sha256(data)
    package = open_package(original)
    main = main_part(package)
    before = _problems(package, main)
    root = package.xml(main)
    document = EditedDocument(
        package,
        main,
        root.find(w("body")),
        Comments(package, main),
        Stamp(author, date, _next_id(package, main)),
    )
    outcomes = []
    for index, operation in enumerate(operations):
        outcome = run_operation(document, index, operation)
        if outcome.status == "refused" and not partial:
            return Report(False, skip_others(operations, outcome), (), input_sha, None)
        outcomes.append(outcome)
    if not any(o.status == "applied" for o in outcomes):
        return Report(False, tuple(outcomes), (nothing_changed(),), input_sha, None)
    package.set_xml(main, root)
    document.comments.save(package, main)
    added = sorted(_problems(package, main) - before)
    if added:
        notice = Notice(
            "SELF_CHECK_FAILED",
            {"problem": added[0]},
            "The edited copy failed SurfSense's own check, so nothing was saved; "
            "report this file to SurfSense.",
        )
        return Report(False, tuple(outcomes), (notice,), input_sha, None)
    written = out.with_name(out.name + ".part")
    package.save(written)
    output = written.read_bytes()
    if output == data:
        written.unlink()
        return Report(False, tuple(outcomes), (nothing_changed(),), input_sha, None)
    written.replace(out)
    return Report(True, tuple(outcomes), (), input_sha, _sha256(output))


def _decide(path: Path, out: Path, decision: Decision, *, drop_comments: bool) -> None:
    package = open_package(path)
    main = main_part(package)
    comment_parts = set(package.related(main, COMMENTS_REL))
    for name in stories(package, main):
        if drop_comments and name in comment_parts:
            continue
        root = package.xml(name)
        changed = decide_all(root, decision)
        if drop_comments:
            changed = strip_anchors(root, None) or changed
        if changed:
            package.set_xml(name, root)
    if drop_comments:
        remove_all_comment_parts(package, main)
    package.save(out)


def accept_all(path: Path, out: Path, *, drop_comments: bool = False) -> None:
    """Every author's changes accepted; with drop_comments, the clean copy without comments."""
    _decide(path, out, "accept", drop_comments=drop_comments)


def reject_all(path: Path, out: Path) -> None:
    """Every author's changes rejected; comments stay."""
    _decide(path, out, "reject", drop_comments=False)


def external(path: Path, out: Path, internal_comment_ids: Collection[str]) -> None:
    """The copy for the other side: internal comments gone with their ranges and marks."""
    ids = {str(i) for i in internal_comment_ids}
    package = open_package(path)
    main = main_part(package)
    comment_parts = set(package.related(main, COMMENTS_REL))
    if ids:
        for name in stories(package, main):
            if name in comment_parts:
                continue
            root = package.xml(name)
            if strip_anchors(root, ids):
                package.set_xml(name, root)
        remove_comments(package, main, ids)
    package.save(out)


def counts(path: Path) -> RevisionCounts:
    """Tracked changes in the body (w:ins, w:del, w:moveFrom, w:moveTo) and comments in the file."""
    package = open_package(path)
    main = main_part(package)
    body = package.xml(main).find(w("body"))
    changes = sum(1 for _ in body.iter(INS, DEL, MOVE_FROM, MOVE_TO))
    comments = sum(
        sum(1 for _ in package.xml(name).iter(w("comment")))
        for name in package.related(main, COMMENTS_REL)
        if name in package.names
    )
    return RevisionCounts(changes, comments)


__all__ = [
    "RevisionCounts",
    "accept_all",
    "apply",
    "counts",
    "external",
    "main_part",
    "reject_all",
]
