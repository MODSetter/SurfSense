"""Where a PDF read from its text layer gets a blank line: where a paragraph, a
heading or a table ends, as the gaps between its lines show, so the chunker cuts
there and not at an arbitrary line."""

from pathlib import Path

import pytest

from tests import pdf_samples
from worker.ingestion.chunking import chunk
from worker.ingestion.pdf_text_layer import read_text_layer

pytestmark = pytest.mark.unit

REPORT = pdf_samples.prose(8, seed=3)
CAPTION = (
    "Table 1. Classification accuracies for naive Bayes and flexible Bayes on"
    " various data sets."
)
ROWS = [
    ["DATA SET", "NAIVE", "FLEXIBLE"],
    ["BREAST", "95.9 ± 0.2", "96.7 ± 0.2"],
    ["CLEVELAND", "83.3 ± 0.6", "80.0 ± 0.6"],
    ["GLASS2", "61.9 ± 1.4", "83.8 ± 0.7"],
    ["CREDIT", "74.8 ± 0.5", "78.3 ± 0.6"],
    ["HORSE", "73.3 ± 0.9", "69.7 ± 1.0"],
    ["VEHICLE", "44.9 ± 0.6", "61.5 ± 0.4"],
]
CAPTIONED = {
    "above, as in a paper": True,
    "below, as in a spec": False,
}


@pytest.fixture(autouse=True)
def switch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default a user has: the text layer on."""
    monkeypatch.delenv("SURFSENSE_LOCAL_PDF_TEXT_LAYER", raising=False)


def read(tmp_path: Path, pdf: bytes) -> str:
    """The upload's text, read as ingest reads it."""
    path = tmp_path / "upload.pdf"
    path.write_bytes(pdf)
    text = read_text_layer(path).text
    assert text is not None
    return text


def block_with(text: str, phrase: str) -> str:
    """The stretch between blank lines that holds the phrase."""
    found = [block for block in text.split("\n\n") if phrase in block]
    assert len(found) == 1, phrase
    return found[0]


def only_line_breaks_added(text: str, to: str) -> bool:
    """Whether text is `to` with "\\n" put in, and not a character moved or lost."""
    at = 0
    for char in text:
        if at < len(to) and char == to[at]:
            at += 1
        elif char != "\n":
            return False
    return at == len(to)


def table(caption_above: bool) -> bytes:
    """Table 1 between report paragraphs, its caption on the side given."""
    return pdf_samples.table_page(
        CAPTION,
        ROWS,
        caption_above=caption_above,
        before=REPORT[:3],
        after=REPORT[3:6],
    )


def test_paragraphs_a_gap_apart_are_a_blank_line_apart(tmp_path: Path) -> None:
    """Their own lines stay together: only the gap between them is a paragraph's end."""
    text = read(tmp_path, pdf_samples.text_pages(REPORT[:4]))

    assert text == pdf_samples.set_text(REPORT[:4])


def test_a_heading_on_its_own_line_goes_with_the_paragraph_under_it(
    tmp_path: Path,
) -> None:
    """On its own, the chunker could leave it at the end of the passage before."""
    pages = (REPORT[:2], ["Capital plan", *REPORT[2:4]])

    text = read(tmp_path, pdf_samples.text_pages(*pages))

    assert block_with(text, "Capital plan").startswith("Capital plan\nParagraph 3 on")
    assert "\n\nParagraph 4 on" in text


@pytest.mark.parametrize("caption_above", CAPTIONED.values(), ids=CAPTIONED)
def test_a_table_keeps_its_caption_header_and_rows_in_one_block(
    tmp_path: Path, caption_above: bool
) -> None:
    """The caption goes with the nearer side; the rule under the header and the
    caption's own gap are not a paragraph's end."""
    text = read(tmp_path, table(caption_above))

    block = block_with(text, "Table 1.")
    assert all(row[0] in block for row in ROWS)
    assert block.startswith("Table 1." if caption_above else "DATA SET")
    assert "Paragraph" not in block


def test_a_table_under_its_caption_stays_in_one_passage(tmp_path: Path) -> None:
    """The page takes three passages. Cut at any line, as before this, the caption
    and header went to one passage and the rows to the next."""
    text = read(tmp_path, table(caption_above=True))

    passages = chunk(text, tokenizer="character", chunk_size=1200)

    assert len(passages) >= 3
    holding = [passage.text for passage in passages if "Table 1." in passage.text]
    assert len(holding) == 1
    assert all(" ".join(row) in holding[0] for row in ROWS)


def test_a_two_column_page_starts_each_paragraph_after_a_blank_line(
    tmp_path: Path,
) -> None:
    """Down one column, then up to the top of the next; the title goes with the
    first paragraph, as a heading does."""
    paragraphs = pdf_samples.prose(10, seed=2)
    pdf = pdf_samples.two_column_page(paragraphs, paragraph_space=6)

    text = read(tmp_path, pdf)

    assert text.startswith("Coastal freight corridors\nParagraph 1 on")
    starts = [text.index(f"\n\nParagraph {n} on") for n in range(2, 11)]
    assert starts == sorted(starts)


@pytest.mark.parametrize(
    "pdf",
    [
        pdf_samples.text_pages(REPORT[:3], REPORT[3:6], REPORT[6:]),
        table(caption_above=True),
        table(caption_above=False),
        pdf_samples.two_column_page(pdf_samples.prose(10, seed=2)),
        pdf_samples.two_column_page(pdf_samples.prose(10, seed=2), paragraph_space=6),
        pdf_samples.illustrated(REPORT[:4]),
        pdf_samples.stamped(
            pdf_samples.text_pages(REPORT[:4]), header="Harbour Annual Report 2025"
        ),
        pdf_samples.lines_page(REPORT[0].split(". ")),
    ],
    ids=[
        "paragraphs",
        "a table captioned above",
        "a table captioned below",
        "two columns",
        "two spaced columns",
        "a photo",
        "a running header",
        "evenly spaced lines",
    ],
)
def test_only_line_breaks_are_added(tmp_path: Path, pdf: bytes) -> None:
    """The A/B measured this text: no character of it is moved, dropped or changed."""
    text = read(tmp_path, pdf)

    assert only_line_breaks_added(text, to=pdf_samples.ab_text(pdf))


def test_a_word_joined_at_a_hyphen_does_not_end_its_paragraph(
    tmp_path: Path,
) -> None:
    """pdfium joins the two halves into one line of text that spans two lines of the
    page: measured from its first line, the next line seemed two lines down."""
    pdf = pdf_samples.lines_page(
        [
            "Hermes Kanban keeps its whole board in one file.",
            "The orchestration layer for the Her-",
            "mes Agent keeps the life-",
            "cycle of every task it runs, and",
            "the board outlives every process.",
            "",
            "Each task is a row in one table, and",
            "each worker claims one row at a time.",
        ]
    )

    text = read(tmp_path, pdf)

    assert text == (
        "Hermes Kanban keeps its whole board in one file.\n"
        "The orchestration layer for the Hermes Agent keeps the lifecycle of every"
        " task it runs, and\nthe board outlives every process.\n\n"
        "Each task is a row in one table, and\neach worker claims one row at a time."
    )


def test_characters_past_u_ffff_do_not_move_the_breaks(tmp_path: Path) -> None:
    """On Windows each takes two of pdfium's text indexes, so every line after one
    was measured at the wrong character."""
    letter, wide = "g", "\U0001d538"
    path = tmp_path / "upload.pdf"
    path.write_bytes(
        pdf_samples.misencoded(pdf_samples.text_pages(REPORT[:4]), letter, wide)
    )

    text = read_text_layer(path).text

    # pypdfium2 documents get_text_range as UCS-2 only; on Windows it reads these.
    if text is None or wide not in text:
        pytest.skip("pdfium here does not give back text past U+FFFF")
    assert text.count(wide) > 20
    assert text == pdf_samples.set_text(REPORT[:4]).replace(letter, wide)
