"""List numbers as Word 16 renders them, rule by rule.

Each case rebuilds a fixture of references/skills_to_improve/shared/tests/fixtures
(numzoo/, wp4/restart_zoo) and expects the ListString Word gave for it, so these
pin where the reader departs from Docling on purpose.
"""

import re
from pathlib import Path

import pytest
from docx import Document
from docx.document import Document as WordDocument
from docx.oxml import parse_xml

from tests.unit.worker.test_word_markdown import W, saved, with_numbering
from worker.ingestion.word_markdown.document import markdown_of

pytestmark = pytest.mark.unit

_SHOWN = re.compile(r"^(?:#+ )?(?:- )?(.*?)\s*p(\d+)$")


def lvl(ilvl: int, num_fmt: str, text: str, start: int = 1, extra: str = "") -> str:
    """One w:lvl; extra goes between its format and its text."""
    return (
        f'<w:lvl w:ilvl="{ilvl}"><w:start w:val="{start}"/>'
        f'<w:numFmt w:val="{num_fmt}"/>{extra}<w:lvlText w:val="{text}"/></w:lvl>'
    )


def abstract(abstract_id: int, *levels: str, extra: str = "") -> str:
    """A w:abstractNum; extra goes before its levels."""
    return f'<w:abstractNum w:abstractNumId="{abstract_id}">{extra}{"".join(levels)}</w:abstractNum>'


def num(num_id: int, abstract_id: int, starts: dict[int, int] | None = None) -> str:
    """A w:num on an abstract list, with a startOverride per level in starts."""
    overrides = "".join(
        f'<w:lvlOverride w:ilvl="{ilvl}"><w:startOverride w:val="{start}"/></w:lvlOverride>'
        for ilvl, start in (starts or {}).items()
    )
    return f'<w:num w:numId="{num_id}"><w:abstractNumId w:val="{abstract_id}"/>{overrides}</w:num>'


def paragraph(
    document: WordDocument, ppr: str = "", num_id: int | None = None, ilvl: int = 0
) -> None:
    """The next paragraph, its text p<n> in order; numbered directly if num_id."""
    n = len(document.paragraphs)
    numbering = (
        ""
        if num_id is None
        else f'<w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{num_id}"/></w:numPr>'
    )
    document.element.body.insert_element_before(
        parse_xml(
            f"<w:p {W}><w:pPr>{ppr}{numbering}</w:pPr><w:r><w:t>p{n}</w:t></w:r></w:p>"
        ),
        "w:sectPr",
    )


def numbers(document: WordDocument, folder: Path) -> list[str]:
    """Each paragraph's number as the markdown shows it, in order."""
    shown = []
    for line in markdown_of(saved(document, folder)).split("\n"):
        if match := _SHOWN.match(line.strip()):
            assert int(match.group(2)) == len(shown), line
            shown.append(match.group(1))
    return shown


def fresh() -> WordDocument:
    """A document whose body holds only its section properties."""
    document = Document()
    body = document.element.body
    for child in list(body):
        if child.tag != f"{{{body.nsmap['w']}}}sectPr":
            body.remove(child)
    return document


def numbered_list(document: WordDocument, *items: tuple[int, int]) -> None:
    """One paragraph per (numId, ilvl), numbered directly."""
    for num_id, ilvl in items:
        paragraph(document, num_id=num_id, ilvl=ilvl)


def test_lvl_restart_names_the_level_whose_items_restart_it(tmp_path: Path) -> None:
    """zoo_lvlrestart: 1 restarts only after level 0; 0 never restarts."""
    document = fresh()
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "decimal", "%1."),
            lvl(1, "decimal", "%1.%2"),
            lvl(2, "lowerLetter", "(%3)", extra='<w:lvlRestart w:val="1"/>'),
            lvl(3, "lowerRoman", "(%4)", extra='<w:lvlRestart w:val="0"/>'),
        ),
        num(1, 0),
    )
    numbered_list(
        document,
        *[(1, ilvl) for ilvl in (0, 1, 2, 2, 1, 2, 3, 0, 1, 2, 3)],
    )

    assert numbers(document, tmp_path) == [
        "1.", "1.1", "(a)", "(b)", "1.2", "(c)", "(i)", "2.", "2.1", "(a)", "(ii)",
    ]  # fmt: skip


def test_legal_numbering_shows_every_level_in_decimal(tmp_path: Path) -> None:
    """zoo_islgl: isLgl writes Article I's sections 1.1; a level without it
    keeps each level's own format."""
    document = fresh()
    legal = "<w:isLgl/>"
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "upperRoman", "Article %1"),
            lvl(1, "decimal", "%1.%2", extra=legal),
            lvl(2, "lowerLetter", "%1.%2.%3", extra=legal),
            lvl(3, "upperLetter", "%1.%2.%3.%4"),
        ),
        num(1, 0),
    )
    numbered_list(document, *[(1, ilvl) for ilvl in (0, 1, 1, 2, 3, 0, 1, 2, 2)])

    assert numbers(document, tmp_path) == [
        "Article I", "1.1", "1.2", "1.2.1", "I.2.a.A", "Article II", "2.1", "2.1.1",
        "2.1.2",
    ]  # fmt: skip


def test_a_num_style_link_borrows_levels_but_keeps_its_own_counters(
    tmp_path: Path,
) -> None:
    """zoo_numstylelink: abstract 1 links to the Legal List style, whose num is
    on abstract 0; nums 2 and 3 count apart from num 1, which uses 0 directly."""
    document = fresh()
    document.styles.element.append(
        parse_xml(
            f'<w:style {W} w:type="numbering" w:styleId="LegalList">'
            '<w:name w:val="Legal List"/>'
            '<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style>'
        )
    )
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "decimal", "%1."),
            lvl(1, "decimal", "%1.%2"),
            extra='<w:styleLink w:val="LegalList"/>',
        )
        + abstract(1, extra='<w:numStyleLink w:val="LegalList"/>'),
        num(1, 0) + num(2, 1) + num(3, 1, {0: 1}),
    )
    numbered_list(document, (2, 0), (2, 1), (1, 0), (2, 0), (3, 0), (3, 1), (1, 0))

    assert numbers(document, tmp_path) == ["1.", "1.1", "1.", "2.", "1.", "1.1", "2."]


def test_a_skipped_level_counts_its_start_and_continues_from_it(
    tmp_path: Path,
) -> None:
    """zoo_direct: level 1 skipped under item 2 still counts 1, so the next
    level-1 item is 2.2. numId 0 is no number; a numPr without ilvl is level 0."""
    document = fresh()
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "decimal", "%1."),
            lvl(1, "decimal", "%1.%2."),
            lvl(2, "lowerLetter", "(%3)"),
            lvl(3, "lowerRoman", "(%4)"),
        ),
        num(1, 0),
    )
    paragraph(document)
    numbered_list(document, *[(1, ilvl) for ilvl in (0, 1, 1, 2, 2, 3, 0, 2, 1)])
    paragraph(document)
    numbered_list(document, (1, 0), (0, 0), (1, 0))
    paragraph(document, '<w:numPr><w:numId w:val="1"/></w:numPr>')

    assert numbers(document, tmp_path) == [
        "", "1.", "1.1.", "1.2.", "(a)", "(b)", "(i)", "2.", "(a)", "2.2.", "", "3.",
        "", "4.", "5.",
    ]  # fmt: skip


def test_start_overrides_set_a_shared_counter_once(tmp_path: Path) -> None:
    """zoo_startoverride: nums on one abstract list share its counters; each
    num's startOverride applies on its first paragraph at that level only."""
    document = fresh()
    with_numbering(
        document,
        abstract(0, lvl(0, "decimal", "%1."), lvl(1, "decimal", "%1.%2")),
        num(1, 0) + num(2, 0, {0: 5}) + num(3, 0, {1: 3}) + num(4, 0, {0: 1}),
    )
    numbered_list(
        document,
        (1, 0), (1, 0), (2, 0), (2, 0), (1, 0), (3, 1), (3, 1), (1, 1), (4, 0),
        (1, 0), (4, 0),
    )  # fmt: skip

    assert numbers(document, tmp_path) == [
        "1.", "2.", "5.", "6.", "7.", "7.3", "7.4", "7.5", "1.", "2.", "3.",
    ]  # fmt: skip


def test_a_reset_level_restarts_from_the_num_that_reset_it(tmp_path: Path) -> None:
    """wp4/restart_zoo: a deeper level restarts from the startOverride of the
    num whose paragraph reset it, not of the num it is in."""
    document = fresh()
    formats = [("decimal", "Article %1"), ("decimal", "%1.%2")]
    formats += [("lowerLetter", "(%3)"), ("lowerRoman", "(%4)")]
    formats += [("decimal", f"%{n}.") for n in range(5, 10)]
    rest = dict.fromkeys(range(4, 9), 1)
    with_numbering(
        document,
        abstract(0, *(lvl(n, f, t) for n, (f, t) in enumerate(formats))),
        num(1, 0)
        + num(5, 0, {0: 5, 1: 7, 2: 5, 3: 4, **rest})
        + num(6, 0, {0: 1, 1: 1, 2: 1, 3: 1, **rest})
        + num(7, 0, {0: 9, 1: 6, 2: 7, 3: 3, **rest})
        + num(8, 0, {1: 5})
        + num(9, 0, {0: 8})
        + num(10, 0, {2: 6})
        + num(11, 0, {0: 20, 1: 8})
        + num(12, 0, {1: 3})
        + num(13, 0, {1: 5, 2: 7})
        + num(14, 0, {2: 6}),
    )
    numbered_list(
        document,
        (1, 0), (1, 1), (1, 2), (1, 2), (5, 2), (5, 3), (5, 1), (5, 2), (1, 2),
        (1, 1), (1, 2), (7, 3), (7, 2), (7, 1), (7, 2), (7, 0), (7, 1), (1, 1),
        (1, 0), (8, 1), (1, 1), (9, 1), (9, 0), (1, 0), (10, 0), (10, 2), (1, 2),
        (11, 0), (11, 1), (1, 1), (12, 2), (12, 1), (1, 1), (6, 1), (6, 2), (1, 1),
        (6, 0), (1, 1), (1, 0), (13, 1), (1, 2), (1, 2), (13, 2), (1, 2), (1, 0),
        (14, 0), (1, 2), (1, 2), (14, 2), (1, 2),
    )  # fmt: skip

    assert numbers(document, tmp_path) == [
        "Article 1", "1.1", "(a)", "(b)", "(e)", "(iv)", "1.2", "(e)", "(f)", "1.3",
        "(a)", "(iii)", "(b)", "1.4", "(g)", "Article 2", "2.6", "2.7", "Article 3",
        "3.5", "3.6", "3.7", "Article 8", "Article 9", "Article 10", "(f)", "(g)",
        "Article 20", "20.8", "20.9", "(a)", "20.3", "20.4", "20.1", "(a)", "20.2",
        "Article 21", "21.1", "Article 22", "22.5", "(g)", "(h)", "(i)", "(j)",
        "Article 23", "Article 24", "(f)", "(g)", "(f)", "(g)",
    ]  # fmt: skip


def test_a_level_a_num_restarts_but_does_not_redefine_shows_nothing(
    tmp_path: Path,
) -> None:
    """zoo_mixed_override: once a num redefines one level with a w:lvl, a level
    it only restarts shows no number, though its counter still moves (10.3)."""
    document = fresh()
    redefined_and_restarted = (
        '<w:num w:numId="2"><w:abstractNumId w:val="0"/>'
        '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="10"/></w:lvlOverride>'
        f'<w:lvlOverride w:ilvl="1">{lvl(1, "lowerLetter", "%2)")}</w:lvlOverride>'
        "</w:num>"
        '<w:num w:numId="3"><w:abstractNumId w:val="0"/>'
        '<w:lvlOverride w:ilvl="1"><w:startOverride w:val="4"/></w:lvlOverride>'
        '<w:lvlOverride w:ilvl="2"><w:startOverride w:val="2"/>'
        f"{lvl(2, 'upperRoman', '[%3]', start=2)}</w:lvlOverride></w:num>"
    )
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "decimal", "%1."),
            lvl(1, "decimal", "%1.%2"),
            lvl(2, "decimal", "%1.%2.%3"),
        )
        + abstract(1, lvl(0, "upperLetter", "%1.")),
        num(1, 0) + redefined_and_restarted + num(4, 1),
    )
    numbered_list(
        document,
        (1, 0), (1, 1), (2, 0), (2, 1), (2, 1), (1, 1), (3, 1), (3, 2), (3, 2),
        (4, 0), (1, 0), (2, 0), (3, 0), (1, 2),
    )  # fmt: skip

    assert numbers(document, tmp_path) == [
        "1.", "1.1", "", "a)", "b)", "10.3", "", "[II]", "[III]", "A.", "11.", "",
        "13.", "13.4.2",
    ]  # fmt: skip


def test_numbering_follows_styles_and_their_links_to_levels(tmp_path: Path) -> None:
    """zoo_style_linked: numbering inherits along w:basedOn; a style naming a
    list but no level is level 0, unless level 0 is tied to another style, and
    then it shows none; numId 0 turns a style's numbering off."""
    document = fresh()
    styles = document.styles.element
    for style_id, numbering in (
        ("Heading1", '<w:numId w:val="1"/>'),
        ("Heading2", '<w:ilvl w:val="1"/><w:numId w:val="1"/>'),
        ("Heading3", '<w:numId w:val="1"/>'),
    ):
        properties = styles.get_by_id(style_id).get_or_add_pPr()
        properties.append(parse_xml(f"<w:numPr {W}>{numbering}</w:numPr>"))
    styles.append(
        parse_xml(
            f'<w:style {W} w:type="paragraph" w:styleId="SubClause">'
            '<w:name w:val="Sub Clause"/><w:basedOn w:val="Heading2"/></w:style>'
        )
    )
    tied = '<w:pStyle w:val="Heading{}"/>'
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "decimal", "%1.", extra=tied.format(1)),
            lvl(1, "decimal", "%1.%2", extra=tied.format(2)),
            lvl(2, "lowerLetter", "(%3)", extra=tied.format(3)),
        ),
        num(1, 0),
    )
    for style in ("Heading1", "Heading2", "Heading2", "Heading3", "Heading3"):
        paragraph(document, f'<w:pStyle w:val="{style}"/>')
    paragraph(document, '<w:pStyle w:val="BodyText"/>')
    for style in ("Heading1", "SubClause", "Heading2"):
        paragraph(document, f'<w:pStyle w:val="{style}"/>')
    paragraph(
        document, '<w:pStyle w:val="Heading1"/><w:numPr><w:numId w:val="0"/></w:numPr>'
    )
    paragraph(document, '<w:pStyle w:val="Heading2"/>')
    paragraph(document, '<w:pStyle w:val="Heading1"/>')
    paragraph(
        document, '<w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="2"/></w:numPr>'
    )
    paragraph(document, '<w:pStyle w:val="Heading2"/>')

    assert numbers(document, tmp_path) == [
        "1.", "1.1", "1.2", "", "", "", "2.", "2.1", "2.2", "", "2.3", "3.", "(a)",
        "3.2",
    ]  # fmt: skip


def test_a_paragraph_whose_mark_is_deleted_is_not_counted(tmp_path: Path) -> None:
    """Accepting the change joins it to the next paragraph, which keeps the number."""
    document = fresh()
    with_numbering(document, abstract(0, lvl(0, "decimal", "%1.")), num(1, 0))
    paragraph(document, num_id=1)
    paragraph(
        document,
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        '<w:rPr><w:del w:id="9" w:author="A" w:date="2026-01-01T00:00:00Z"/></w:rPr>',
    )
    paragraph(document, num_id=1)

    assert numbers(document, tmp_path) == ["1.", "", "2."]


def test_number_formats_render_as_word_writes_them(tmp_path: Path) -> None:
    """zoo_formats. A bullet's glyph and a none level both read as a plain item."""
    document = fresh()
    formats = [
        ("decimalZero", "%1."), ("upperLetter", "%2."), ("lowerRoman", "%3)"),
        ("ordinal", "%4"), ("cardinalText", "%5"), ("ordinalText", "%6"),
        ("bullet", ""), ("none", ""),
    ]  # fmt: skip
    with_numbering(
        document,
        abstract(
            0,
            *(lvl(n, f, t) for n, (f, t) in enumerate(formats)),
            lvl(8, "upperRoman", "%9.", start=4),
        )
        + abstract(1, lvl(0, "decimal", "Section %1:"), lvl(1, "decimal", "%1.%2", 0))
        + abstract(2, lvl(0, "chicago", "%1"), lvl(1, "decimalEnclosedCircle", "%2")),
        num(1, 0) + num(2, 1) + num(3, 2),
    )
    numbered_list(document, (1, 0), (1, 0), (1, 0))
    numbered_list(document, *[(1, ilvl) for ilvl in range(1, 9) for _ in range(2)])
    numbered_list(document, (2, 0), (2, 1), (2, 1), (3, 0), (3, 0), (3, 0))
    numbered_list(document, (3, 1), (3, 1))

    assert numbers(document, tmp_path) == [
        "01.", "02.", "03.", "A.", "B.", "i)", "ii)", "1st", "2nd", "One", "Two",
        "First", "Second", "", "", "", "", "IV.", "V.", "Section 1:", "1.0", "1.1",
        "*", "†", "‡", "①", "②",
    ]  # fmt: skip


def test_a_huge_start_keeps_each_marker_short(tmp_path: Path) -> None:
    """w:start comes from the file: letters, numerals and daggers repeat with the
    count, so one in the millions is written in decimal, and one past what a
    32-bit counter holds is ignored."""
    document = fresh()
    with_numbering(
        document,
        abstract(
            0,
            lvl(0, "chicago", "%1", start=40_000_000),
            lvl(1, "lowerLetter", "%2)", start=2_000_000_000),
            lvl(2, "upperRoman", "%3.", start=10**30),
            lvl(3, "decimal", "%4" * 5000),
        ),
        num(1, 0),
    )
    numbered_list(document, *[(1, 0)] * 5, (1, 1), (1, 2), (1, 3))

    shown = numbers(document, tmp_path)

    assert shown[:7] == [
        "40000000", "40000001", "40000002", "40000003", "40000004", "2000000000)",
        "I.",
    ]  # fmt: skip
    assert shown[7].startswith("1111") and len(shown[7]) <= 255
