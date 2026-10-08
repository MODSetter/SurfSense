"""The four Word operations, each checked in full before it changes anything.

A refusal therefore never leaves a half-done edit behind, which `partial` relies on.
"""

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lxml import etree

from modules.artifacts.revised_copies.engines import report as reports
from modules.artifacts.revised_copies.engines.package import Package
from modules.artifacts.revised_copies.engines.report import OpOutcome
from modules.artifacts.revised_copies.engines.word_comments import (
    Comments,
    range_end,
    range_start,
    reference_run,
)
from modules.artifacts.revised_copies.engines.word_text import (
    Match,
    Paragraph,
    QuoteError,
    find,
    normalize_quote,
    one_paragraph,
    paragraphs,
)
from modules.artifacts.revised_copies.engines.word_tracking import (
    Stamp,
    copied_paragraph_props,
    delete_runs,
    insertion,
    isolate,
    mark_paragraph,
    paragraph_mark,
    place_after,
    place_before,
    run_ending_at,
    run_starting_at,
    runs_between,
)
from modules.artifacts.revised_copies.engines.word_xml import (
    BLOCKS,
    DEL,
    FLD_CHAR,
    FLD_SIMPLE,
    INS,
    PPR,
    RPR,
    SECTPR,
    STYLES_REL,
    P,
    T,
    make,
    w,
)

WORD_OPS = ("replace_text", "insert_paragraphs", "delete_paragraphs", "add_comment")
_TOKENS = re.compile(r"\s+|\w+|[^\w\s]")
# Characters XML 1.0 cannot hold; lxml raises on them mid-edit.
_NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")


@dataclass
class EditedDocument:
    package: Package
    main_part: str
    body: etree._Element
    comments: Comments
    stamp: Stamp


class _RefusalError(Exception):
    def __init__(self, code: str, values: dict[str, str | int], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.values = values
        self.message = message


class _BadFieldError(Exception):
    def __init__(self, field: str, why: str) -> None:
        super().__init__(why)
        self.field = field
        self.why = why


def run_operation(document: EditedDocument, index: int, operation: Any) -> OpOutcome:
    op = reports.op_name(operation)
    if op == "?":
        return reports.bad_operation(
            index, op, "op", "every operation needs an op name."
        )
    if op not in WORD_OPS:
        return reports.unsupported(index, op, "docx")
    try:
        values = _HANDLERS[op](document, operation)
    except _BadFieldError as bad:
        return reports.bad_operation(index, op, bad.field, bad.why)
    except (QuoteError, _RefusalError) as refusal:
        return reports.refused(index, op, refusal.code, refusal.values, refusal.message)
    return reports.applied(index, op, values)


def _string(
    operation: dict, field: str, *, required: bool, empty_ok: bool = False
) -> str | None:
    value = operation.get(field)
    if value is None:
        if required:
            raise _BadFieldError(field, "this field is required.")
        return None
    if not isinstance(value, str):
        raise _BadFieldError(field, "must be a string.")
    if _NOT_XML.search(value):
        raise _BadFieldError(field, "holds a control character Word cannot store.")
    if not empty_ok and not value.strip():
        raise _BadFieldError(field, "must not be empty.")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _quote(
    operation: dict, field: str = "quote", *, required: bool = True
) -> str | None:
    value = _string(operation, field, required=required)
    if value is not None and not normalize_quote(value):
        raise _BadFieldError(field, "must hold some text.")
    return value


def _comment_fields(operation: dict, field: str = "comment") -> str | None:
    text = _string(operation, field, required=False)
    internal = operation.get("internal")
    if internal is not None and not isinstance(internal, bool):
        raise _BadFieldError("internal", "must be true or false.")
    return text


def _shown(quote: str) -> str:
    return quote if len(quote) <= 120 else quote[:117] + "..."


def _in_field(quote: str) -> _RefusalError:
    return _RefusalError(
        "QUOTE_IN_FIELD",
        {"quote": _shown(quote)},
        "The quote is inside a field (a page number, date or cross-reference), "
        "which SurfSense does not edit; quote text outside it.",
    )


def _comment(document: EditedDocument, text: str | None) -> str | None:
    return None if text is None else document.comments.add(text, document.stamp)


def _props_of(run: etree._Element) -> etree._Element | None:
    props = run.find(RPR)
    return None if props is None else copy.deepcopy(props)


# replace_text


def _same(a: str, b: str) -> bool:
    return a == b or (a.isspace() and b.isspace())


def _narrow(old: str, new: str) -> tuple[int, int, str]:
    """Trim the words both texts share at either end, so only what differs is marked."""
    before, after = _TOKENS.findall(old), _TOKENS.findall(new)
    shared = min(len(before), len(after))
    head = 0
    while head < shared and _same(before[head], after[head]):
        head += 1
    tail = 0
    while tail < shared - head and _same(before[-1 - tail], after[-1 - tail]):
        tail += 1
    start = sum(len(token) for token in before[:head])
    end = len(old) - sum(len(token) for token in before[len(before) - tail :])
    return start, end, "".join(after[head : len(after) - tail])


def _widen(text: str, start: int, end: int) -> tuple[int, int]:
    """A deletion takes one space with it, so no double space or space before punctuation is left."""
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if after == " " and before in ("", " "):
        return start, end + 1
    if before == " " and (after == "" or after in ".,;:!?)"):
        return start - 1, end
    return start, end


def _replace_text(document: EditedDocument, operation: dict) -> dict[str, str | int]:
    quote = _quote(operation)
    text = _string(operation, "text", required=True, empty_ok=True)
    note = _comment_fields(operation)
    if "\n" in text:
        raise _RefusalError(
            "NEWLINE_IN_TEXT",
            {},
            "replace_text stays inside one paragraph; use insert_paragraphs for new paragraphs.",
        )
    match = find(paragraphs(document.body), quote)
    if any(atom.in_field for atom in match.atoms):
        raise _in_field(quote)
    old = match.paragraph.text[match.start : match.end]
    start, end, new = _narrow(old, text)
    if start >= end and not new:
        raise _RefusalError(
            "SAME_TEXT",
            {"quote": _shown(quote)},
            "text is the same as the quote, so there is nothing to change.",
        )
    paragraph = match.paragraph
    start, end = match.start + start, match.start + end
    if not new:
        start, end = _widen(paragraph.text, start, end)
    stamp = document.stamp
    comment_id = _comment(document, note)
    if end > start:
        first = paragraph.atoms[paragraph.spans[start][0]]
        last = paragraph.atoms[paragraph.spans[end - 1][1]]
        props = _props_of(first.run)
        start_run, end_run = isolate(first, last)
        home = start_run.getparent()
        runs = one_paragraph(paragraph.element).runs
        removed = delete_runs(runs_between(runs, start_run, end_run), stamp)
        added = None
        if new:
            added = insertion(new, props, stamp)
            place_after([d for d in removed if d.getparent() is home][-1], added, stamp)
        first_mark, last_mark = removed[0], added if added is not None else removed[-1]
    else:
        added = _insert_at(paragraph, start, new, match.start, stamp)
        first_mark = last_mark = added
    values: dict[str, str | int] = {}
    if comment_id is not None:
        _anchor(first_mark, last_mark, comment_id, stamp)
        values["comment_id"] = comment_id
    return values


def _insert_at(
    paragraph: Paragraph, position: int, text: str, quote_start: int, stamp: Stamp
) -> etree._Element:
    """Insert before the character at `position`, in the format of the text it joins.

    At the quote's start it joins the quote's first run, never the text before it.
    """
    if position > quote_start:
        before = paragraph.atoms[paragraph.spans[position - 1][1]]
        added = insertion(text, _props_of(before.run), stamp)
        place_after(run_ending_at(before), added, stamp)
    else:
        following = paragraph.atoms[paragraph.spans[position][0]]
        added = insertion(text, _props_of(following.run), stamp)
        place_before(run_starting_at(following), added, stamp)
    return added


def _anchor(
    first: etree._Element, last: etree._Element, comment_id: str, stamp: Stamp
) -> None:
    """A comment's range from `first` to `last`, its reference mark right after."""
    place_before(first, range_start(comment_id), stamp)
    end = range_end(comment_id)
    place_after(last, end, stamp)
    end.addnext(reference_run(comment_id))


# insert_paragraphs


def _style_id(document: EditedDocument, style: str) -> str:
    for name in document.package.related(document.main_part, STYLES_REL):
        if name not in document.package.names:
            continue
        for element in document.package.xml(name).iter(w("style")):
            if element.get(w("type")) != "paragraph":
                continue
            style_id = element.get(w("styleId"), "")
            label = element.find(w("name"))
            label_text = label.get(w("val"), "") if label is not None else ""
            if style in (style_id, label_text) or style.lower() in (
                style_id.lower(),
                label_text.lower(),
            ):
                return style_id
    raise _RefusalError(
        "STYLE_NOT_FOUND",
        {"style": style},
        f"The document has no paragraph style {style!r}; leave style out to match the paragraph quoted.",
    )


def _insert_paragraphs(
    document: EditedDocument, operation: dict
) -> dict[str, str | int]:
    quote = _quote(operation)
    text = _string(operation, "text", required=True, empty_ok=True)
    style = _string(operation, "style", required=False)
    note = _comment_fields(operation)
    match = find(paragraphs(document.body), quote)
    style_id = _style_id(document, style) if style is not None else None
    anchor = match.paragraph.element
    if style_id is None:
        props = copied_paragraph_props(anchor)
        run_props = _props_of(match.atoms[0].run)
    else:
        props = etree.Element(PPR)
        props.append(make("pStyle", val=style_id))
        run_props = None
    stamp = document.stamp
    comment_id = _comment(document, note)
    added = []
    previous = anchor
    for line in text.split("\n"):
        paragraph = etree.Element(P)
        if props is not None:
            paragraph.append(copy.deepcopy(props))
        if line:
            paragraph.append(insertion(line, run_props, stamp))
        mark_paragraph(paragraph, INS, stamp)
        previous.addnext(paragraph)
        previous = paragraph
        added.append(paragraph)
    values: dict[str, str | int] = {"paragraphs": len(added)}
    if comment_id is not None:
        _anchor_paragraphs(added[0], added[-1], comment_id)
        values["comment_id"] = comment_id
    return values


def _anchor_paragraphs(
    first: etree._Element, last: etree._Element, comment_id: str
) -> None:
    props = first.find(PPR)
    first.insert(
        first.index(props) + 1 if props is not None else 0, range_start(comment_id)
    )
    last.append(range_end(comment_id))
    last.append(reference_run(comment_id))


# delete_paragraphs


def _locate(found: list[Paragraph], quote: str) -> int:
    match: Match = find(found, quote)
    return found.index(match.paragraph)


def _check_fields(group: list[Paragraph], quote: str) -> None:
    """A deletion may hold whole fields, never part of one."""
    inside = {id(atom.node) for p in group for atom in p.atoms if atom.in_field}
    depth = 0
    for paragraph in group:
        for run in paragraph.runs:
            simple = any(a.tag == FLD_SIMPLE for a in run.iterancestors())
            for node in run:
                if node.tag == FLD_CHAR:
                    kind = node.get(w("fldCharType"))
                    depth += kind == "begin"
                    depth -= kind == "end"
                    if depth < 0:
                        raise _in_field(quote)
                elif node.tag == T and id(node) in inside and depth == 0 and not simple:
                    raise _in_field(quote)
    if depth:
        raise _in_field(quote)


def _next_block(element: etree._Element) -> etree._Element | None:
    for sibling in element.itersiblings():
        if sibling.tag in BLOCKS or sibling.tag == SECTPR:
            return sibling
    return None


def _delete_paragraphs(
    document: EditedDocument, operation: dict
) -> dict[str, str | int]:
    quote = _quote(operation)
    through = _quote(operation, "through", required=False)
    note = _comment_fields(operation)
    found = paragraphs(document.body)
    first = _locate(found, quote)
    last = _locate(found, through) if through is not None else first
    if last < first:
        raise _RefusalError(
            "THROUGH_BEFORE_QUOTE",
            {"quote": _shown(quote), "through": _shown(through or "")},
            "through must quote the last paragraph to delete, after the quote's paragraph.",
        )
    start, end = found[first].element, found[last].element
    parent = start.getparent()
    between = [start, *_until(start, end)]
    if end.getparent() is not parent or any(
        e.tag in BLOCKS and e.tag != P for e in between
    ):
        raise _RefusalError(
            "RANGE_NOT_CONTIGUOUS",
            {"quote": _shown(quote), "through": _shown(through or quote)},
            "A table or content control lies between the two quotes; delete the paragraphs "
            "on each side in separate operations.",
        )
    group = [p for p in found[first : last + 1] if p.element.getparent() is parent]
    _check_fields(group, quote)
    stamp = document.stamp
    comment_id = _comment(document, note)
    for paragraph in group:
        delete_runs(paragraph.runs, stamp)
        element = paragraph.element
        following = _next_block(element)
        if (
            paragraph_mark(element, DEL) is None
            and element.find(f"{PPR}/{SECTPR}") is None
            and following is not None
            and following.tag != SECTPR
        ):
            mark_paragraph(element, DEL, stamp)
    values: dict[str, str | int] = {"paragraphs": len(group)}
    if comment_id is not None:
        _anchor_paragraphs(start, end, comment_id)
        values["comment_id"] = comment_id
    return values


def _until(start: etree._Element, end: etree._Element) -> list[etree._Element]:
    if start is end:
        return []
    found = []
    for sibling in start.itersiblings():
        found.append(sibling)
        if sibling is end:
            return found
    return found


# add_comment


def _add_comment(document: EditedDocument, operation: dict) -> dict[str, str | int]:
    quote = _quote(operation)
    text = _string(operation, "text", required=True)
    _comment_fields(operation, "text")
    match = find(paragraphs(document.body), quote)
    atoms = match.atoms
    comment_id = _comment(document, text)
    start_run, end_run = isolate(atoms[0], atoms[-1])
    _anchor(start_run, end_run, comment_id, document.stamp)
    return {"comment_id": comment_id}


_HANDLERS: dict[str, Callable[[EditedDocument, dict], dict[str, str | int]]] = {
    "replace_text": _replace_text,
    "insert_paragraphs": _insert_paragraphs,
    "delete_paragraphs": _delete_paragraphs,
    "add_comment": _add_comment,
}
