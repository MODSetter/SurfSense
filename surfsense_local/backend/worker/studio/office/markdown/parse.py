"""Markdown to blocks, through markdown-it-py's CommonMark parser with GFM tables."""

import re

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from worker.studio.office.markdown.blocks import (
    Block,
    Code,
    Figure,
    Heading,
    ListBlock,
    Paragraph,
    Quote,
    Rule,
    Span,
    Spans,
    Table,
)
from worker.studio.office.markdown.chart import read_chart

FIGURE_SCHEME = "image:"
# Raw HTML stays text: nothing the model wrote is interpreted as markup.
# CommonMark's preset stops at 20 levels of tokens (a list level is two) and
# silently drops what is deeper; 100 keeps the text of any plausible document.
_PARSER = MarkdownIt("commonmark", {"html": False, "maxNesting": 100}).enable(
    ["table", "strikethrough"]
)
# What XML 1.0 cannot hold and python-docx refuses: control characters,
# surrogates and the non-characters U+FFFE and U+FFFF.
_NOT_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


def parse_markdown(text: str) -> list[Block]:
    return _blocks(SyntaxTreeNode(_PARSER.parse(_NOT_XML.sub("", text))).children)


def _blocks(nodes: list[SyntaxTreeNode]) -> list[Block]:
    blocks: list[Block] = []
    for node in nodes:
        blocks.extend(_block(node))
    return blocks


def _block(node: SyntaxTreeNode) -> list[Block]:
    match node.type:
        case "heading":
            return [Heading(int(node.tag[1:]), _spans(node.children[0]))]
        case "paragraph":
            return _paragraph(node.children[0])
        case "bullet_list" | "ordered_list":
            items = tuple(tuple(_blocks(item.children)) for item in node.children)
            return [ListBlock(node.type == "ordered_list", items)]
        case "table":
            return [_table(node)]
        case "fence" if node.info.strip().lower() == "chart":
            return [read_chart(node.content)]
        case "fence" | "code_block":
            return [Code(node.content.rstrip("\n"))]
        case "blockquote":
            return [Quote(tuple(_blocks(node.children)))]
        case "hr":
            return [Rule()]
        case _:
            return [Paragraph((Span(node.content),))] if node.content.strip() else []


def _paragraph(inline: SyntaxTreeNode) -> list[Block]:
    """A paragraph, split around any image in it: a figure stands on its own."""
    blocks: list[Block] = []
    pending: list[Span] = []
    for child in inline.children:
        if child.type == "image":
            if _has_text(pending):
                blocks.append(Paragraph(_trimmed(pending)))
            pending = []
            blocks.append(_figure(child))
        else:
            pending.extend(_inline(child, Span("")))
    if _has_text(pending):
        blocks.append(Paragraph(_trimmed(pending)))
    return blocks


def _figure(image: SyntaxTreeNode) -> Figure:
    target = str(image.attrs.get("src", ""))
    caption = "".join(span.text for span in _spans(image)).strip()
    name = target[len(FIGURE_SCHEME) :] if target.startswith(FIGURE_SCHEME) else None
    return Figure(name=name or None, caption=caption or (name or target))


def _table(node: SyntaxTreeNode) -> Table:
    sections = {section.type: section for section in node.children}
    head_rows = sections["thead"].children if "thead" in sections else []
    body_rows = sections["tbody"].children if "tbody" in sections else []
    header = tuple(_cell(cell) for cell in head_rows[0].children) if head_rows else ()
    rows = tuple(tuple(_cell(cell) for cell in row.children) for row in body_rows)
    return Table(header=header, rows=rows)


def _cell(cell: SyntaxTreeNode) -> Spans:
    return _spans(cell.children[0]) if cell.children else ()


def _spans(inline: SyntaxTreeNode) -> Spans:
    spans: list[Span] = []
    for child in inline.children:
        spans.extend(_inline(child, Span("")))
    return tuple(span for span in spans if span.text)


def _inline(node: SyntaxTreeNode, marks: Span) -> list[Span]:
    match node.type:
        case "text" | "html_inline":
            return [_with(marks, node.content)]
        case "code_inline":
            return [_with(marks, node.content, code=True)]
        case "softbreak":
            return [_with(marks, " ")]
        case "hardbreak":
            return [_with(marks, "\n")]
        case "strong":
            return _children(node, _marked(marks, bold=True))
        case "em":
            return _children(node, _marked(marks, italic=True))
        case "s":
            return _children(node, _marked(marks, strike=True))
        case "link":
            return _children(node, _marked(marks, href=str(node.attrs.get("href", ""))))
        case "image":
            # Inside a link or a heading: only its caption can stand there.
            return _children(node, _marked(marks, italic=True))
        case _:
            return _children(node, marks)


def _children(node: SyntaxTreeNode, marks: Span) -> list[Span]:
    spans: list[Span] = []
    for child in node.children:
        spans.extend(_inline(child, marks))
    return spans


def _marked(marks: Span, **changes: object) -> Span:
    return Span(
        "",
        bold=bool(changes.get("bold", marks.bold)),
        italic=bool(changes.get("italic", marks.italic)),
        code=marks.code,
        strike=bool(changes.get("strike", marks.strike)),
        href=changes.get("href", marks.href) or None,  # type: ignore[arg-type]
    )


def _with(marks: Span, text: str, *, code: bool = False) -> Span:
    return Span(
        text,
        bold=marks.bold,
        italic=marks.italic,
        code=code or marks.code,
        strike=marks.strike,
        href=marks.href,
    )


def _has_text(spans: list[Span]) -> bool:
    return any(span.text.strip() for span in spans)


def _trimmed(spans: list[Span]) -> Spans:
    """Drop the space an image split left at either end of a paragraph."""
    kept = [span for span in spans if span.text]
    if kept:
        kept[0] = _with(kept[0], kept[0].text.lstrip(), code=kept[0].code)
        kept[-1] = _with(kept[-1], kept[-1].text.rstrip(), code=kept[-1].code)
    return tuple(span for span in kept if span.text)
