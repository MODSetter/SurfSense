"""Word files for the engine tests, and the readers and checks that judge its output.

The readers here are written independently of the engine, so a test never grades
the engine with its own code.
"""

import zipfile
from collections import Counter
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from lxml import etree

from modules.artifacts.revised_copies.engines.package import (
    open_package,
    package_problems,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENTS_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
)
COMMENTS_REL = f"{R}/comments"
HYPERLINK_REL = f"{R}/hyperlink"
DATE = "2026-01-02T03:04:05Z"


def w(tag: str) -> str:
    """A WordprocessingML tag name."""
    return f"{{{W}}}{tag}"


def run(text: str, *, bold: bool = False, italic: bool = False) -> str:
    """One run, with optional bold or italic, as XML."""
    props = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "")
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'


def para(*runs: str, ppr: str = "") -> str:
    """One paragraph of runs, as XML."""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def inserted(id_: int, author: str, *runs: str) -> str:
    """Runs inside another author's tracked insertion, as XML."""
    return f'<w:ins w:id="{id_}" w:author="{author}" w:date="{DATE}">{"".join(runs)}</w:ins>'


def deleted(id_: int, author: str, text: str) -> str:
    """Text inside another author's tracked deletion, as XML."""
    return (
        f'<w:del w:id="{id_}" w:author="{author}" w:date="{DATE}">'
        f'<w:r><w:delText xml:space="preserve">{text}</w:delText></w:r></w:del>'
    )


def docx_with_body(
    tmp_path: Path,
    body: str,
    *,
    comments: list[tuple[int, str, str]] | None = None,
    name: str = "in.docx",
) -> Path:
    """A real Word file (python-docx's template) whose body is the given XML."""
    base = tmp_path / f"base-{name}"
    docx.Document().save(str(base))
    with zipfile.ZipFile(base) as archive:
        parts = {info.filename: archive.read(info) for info in archive.infolist()}
    parts["word/document.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>'
    ).encode()
    rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
    link = etree.SubElement(rels, f"{{{PR}}}Relationship")
    link.attrib.update(
        {
            "Id": "rIdLink",
            "Type": HYPERLINK_REL,
            "Target": "https://example.com/terms",
            "TargetMode": "External",
        }
    )
    if comments is not None:
        parts["word/comments.xml"] = _comments_xml(comments)
        rel = etree.SubElement(rels, f"{{{PR}}}Relationship")
        rel.attrib.update(
            {"Id": "rIdComments", "Type": COMMENTS_REL, "Target": "comments.xml"}
        )
        types = etree.fromstring(parts["[Content_Types].xml"])
        override = etree.SubElement(types, f"{{{CT}}}Override")
        override.attrib.update(
            {"PartName": "/word/comments.xml", "ContentType": COMMENTS_TYPE}
        )
        parts["[Content_Types].xml"] = etree.tostring(
            types, xml_declaration=True, encoding="UTF-8", standalone=True
        )
    parts["word/_rels/document.xml.rels"] = etree.tostring(
        rels, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    path = tmp_path / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for part, data in parts.items():
            archive.writestr(part, data)
    return path


def _comments_xml(comments: list[tuple[int, str, str]]) -> bytes:
    items = "".join(
        f'<w:comment w:id="{id_}" w:author="{author}" w:date="{DATE}" w:initials="X">'
        f"<w:p><w:r><w:annotationRef/></w:r><w:r><w:t>{text}</w:t></w:r></w:p></w:comment>"
        for id_, author, text in comments
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:comments xmlns:w="{W}">{items}</w:comments>'
    ).encode()


def rich_docx(tmp_path: Path, name: str = "rich.docx") -> Path:
    """A python-docx file with a heading, a numbered list, a table, header and footer."""
    document = docx.Document()
    section = document.sections[0]
    section.header.paragraphs[0].text = "Confidential header"
    section.footer.paragraphs[0].text = "Footer of the agreement"
    document.add_heading("Master Services Agreement", level=1)
    intro = document.add_paragraph("This agreement is between Acme and Beta.")
    intro.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    document.add_paragraph("First obligation of the parties.", style="List Number")
    document.add_paragraph("Second obligation of the parties.", style="List Number")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Fee"
    table.cell(0, 1).text = "100 dollars"
    table.cell(1, 0).text = "Term"
    table.cell(1, 1).text = "Twelve months"
    document.add_paragraph("Payment is due within 30 days of invoice.")
    document.add_paragraph("Closing words.")
    path = tmp_path / name
    document.save(str(path))
    return path


def _body(path: Path) -> etree._Element:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    return root.find(w("body"))


def _paragraphs(root: etree._Element) -> list[etree._Element]:
    return [
        p
        for p in root.iter(w("p"))
        if not any(a.tag == w("txbxContent") for a in p.iterancestors())
    ]


def _live(node: etree._Element) -> bool:
    """Not deleted; a text box inside a deleted run keeps its own text."""
    for ancestor in node.iterancestors():
        if ancestor.tag == w("txbxContent"):
            return True
        if ancestor.tag in (w("del"), w("moveFrom")):
            return False
    return True


def text_now(path: Path) -> list[str]:
    """Each body paragraph as it reads with every change shown: insertions in, deletions out."""
    lines = []
    for p in _paragraphs(_body(path)):
        pieces = []
        for node in p.iter(w("t"), w("tab")):
            if not _live(node) or any(
                a.tag == w("txbxContent") for a in node.iterancestors()
            ):
                continue
            pieces.append("\t" if node.tag == w("tab") else node.text or "")
        lines.append("".join(pieces))
    return lines


def plain_text(path: Path) -> list[str]:
    """Body paragraphs of a file that must hold no tracked changes at all."""
    body = _body(path)
    leftovers = [
        el.tag
        for el in body.iter(
            w("ins"), w("del"), w("moveFrom"), w("moveTo"), w("delText")
        )
    ]
    assert leftovers == [], f"revisions left: {leftovers}"
    return text_now(path)


def revision_authors(path: Path) -> Counter:
    """How many w:ins and w:del in the body each author has."""
    body = _body(path)
    return Counter(el.get(w("author")) for el in body.iter(w("ins"), w("del")))


def comments_of(path: Path) -> dict[str, tuple[str, str]]:
    """Comment id -> (author, text) from the comments part, or nothing when absent."""
    package = open_package(path)
    main = "word/document.xml"
    names = package.related(main, COMMENTS_REL)
    if not names:
        return {}
    root = package.xml(names[0])
    return {
        c.get(w("id")): (
            c.get(w("author")),
            "\n".join(
                "".join(t.text or "" for t in p.iter(w("t"))) for p in c.iter(w("p"))
            ),
        )
        for c in root.iter(w("comment"))
    }


def anchored_text(path: Path, comment_id: str) -> str:
    """The text, as it reads now, between a comment's range start and end."""
    body = _body(path)
    inside = False
    pieces = []
    for el in body.iter():
        if el.tag == w("commentRangeStart") and el.get(w("id")) == comment_id:
            inside = True
        elif el.tag == w("commentRangeEnd") and el.get(w("id")) == comment_id:
            break
        elif inside and el.tag == w("t") and _live(el):
            pieces.append(el.text or "")
    return "".join(pieces)


def structure_problems(path: Path) -> list[str]:
    """What would make Word refuse or repair the file, as found by an independent check."""
    package = open_package(path)
    problems = list(package_problems(package))
    try:
        docx.Document(str(path))
    except Exception as error:  # python-docx raises many types for a broken file
        problems.append(f"python-docx cannot open it: {error!r}")
    stories = [
        name
        for name in package.names
        if name.startswith("word/")
        and name.endswith(".xml")
        and "wordprocessingml" in (package.content_type(name) or "")
    ]
    revision_ids: Counter = Counter()
    comment_ids: set[str] = set()
    starts: Counter = Counter()
    ends: Counter = Counter()
    references: Counter = Counter()
    for name in stories:
        root = package.xml(name)
        for el in root.iter(w("ins"), w("del"), w("moveFrom"), w("moveTo")):
            revision_ids[el.get(w("id"))] += 1
            if not el.get(w("author")) or not el.get(w("date")):
                problems.append(f"{name}: a revision without author or date")
        for el in root.iter(w("t")):
            if not _live(el):
                problems.append(f"{name}: w:t inside a deletion")
        for el in root.iter(w("delText")):
            if _live(el):
                problems.append(f"{name}: w:delText outside a deletion")
        if root.tag == w("comments"):
            ids = [c.get(w("id")) for c in root.iter(w("comment"))]
            if len(ids) != len(set(ids)):
                problems.append("comment ids repeat")
            comment_ids.update(ids)
        for el in root.iter(w("commentRangeStart")):
            starts[el.get(w("id"))] += 1
        for el in root.iter(w("commentRangeEnd")):
            ends[el.get(w("id"))] += 1
        for el in root.iter(w("commentReference")):
            references[el.get(w("id"))] += 1
    problems.extend(
        f"revision id {i} repeats" for i, n in revision_ids.items() if n > 1
    )
    for kind, counter in (("start", starts), ("end", ends), ("reference", references)):
        for id_, n in counter.items():
            if id_ not in comment_ids:
                problems.append(f"comment {kind} {id_} has no comment")
            if n > 1:
                problems.append(f"comment {kind} {id_} repeats")
    for id_ in comment_ids:
        if starts[id_] != ends[id_]:
            problems.append(f"comment {id_} range is unbalanced")
    return problems
