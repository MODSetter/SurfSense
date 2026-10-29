"""A MOBI or AZW3 book's bytes read back as the HTML it holds."""

import time
from contextlib import suppress

import pytest

from modules.documents.kindle_books.container import DrmProtectedError, KindleBookError
from tests import kindle_samples
from worker.ingestion.kindle_books.reading import book_html

pytestmark = pytest.mark.unit

CHAPTER = (
    "<h2>Loomings</h2><p>Call me Ishmael. Some years ago, never mind how long.</p>"
)


def test_an_uncompressed_book_reads_back_its_html() -> None:
    """kindlegen -c0 stores the HTML as it is."""
    html = book_html(kindle_samples.mobi(f"<html><body>{CHAPTER}</body></html>"))

    assert CHAPTER in html


def test_a_palmdoc_book_reads_back_its_html() -> None:
    """calibre's compression: literals, runs, space pairs and overlapping copies."""
    long = CHAPTER * 40 + "<p>Aaaaaaaaaaaaaaaaaaaa! Café, naïve, 東京.</p>"

    html = book_html(kindle_samples.mobi(long, compression=2))

    assert html == long


def test_the_bytes_a_writer_trails_after_each_record_are_left_out() -> None:
    """The header's flags name them; read as text, they would land mid-sentence."""
    long = CHAPTER * 200

    html = book_html(kindle_samples.mobi(long, compression=2, trailing=True))

    assert html == long


def test_a_huffcdic_book_reads_back_its_html() -> None:
    """kindlegen's compression, a dictionary entry that is itself compressed included."""
    html = book_html(kindle_samples.mobi(CHAPTER * 200, compression=17480))

    assert html == CHAPTER * 200


def test_a_kf8_book_puts_each_file_back_together_in_order() -> None:
    """An AZW3 stores each file as a skeleton plus fragments to insert into it."""
    first = ["<h2>Loomings</h2>", "<p>Call me Ishmael.</p>"]
    second = ["<h2>The Carpet-Bag</h2><p>I stuffed a shirt or two.</p>"]

    html = book_html(kindle_samples.azw3([first, second]))

    assert "".join(first) in html
    assert html.index("Call me Ishmael.") < html.index("The Carpet-Bag")
    # Fragments land inside the body, not after the closing tags.
    assert html.count("<body") == 1 and html.rstrip().endswith("</html>")


def test_a_combined_file_is_read_from_its_kf8_copy() -> None:
    """kindlegen keeps an old MOBI copy beside the KF8 one; KF8 keeps the real markup."""
    book = kindle_samples.combined(
        "<p>The MOBI 6 copy.</p>", [["<h2>Loomings</h2>", "<p>The KF8 copy.</p>"]]
    )

    html = book_html(book)

    assert "The KF8 copy." in html
    assert "The MOBI 6 copy." not in html


def test_a_combined_file_falls_back_to_its_mobi_copy_when_kf8_is_damaged() -> None:
    """The MOBI 6 copy holds the same text, without the KF8 markup."""
    book = kindle_samples.combined(
        "<p>The MOBI 6 copy.</p>", [["<p>The KF8 copy.</p>"]], damaged_kf8=True
    )

    assert "The MOBI 6 copy." in book_html(book)


SAMPLES = {
    "palmdoc": kindle_samples.mobi(CHAPTER * 3, compression=2, trailing=True),
    "huffcdic": kindle_samples.mobi(CHAPTER * 3, compression=17480),
    "kf8": kindle_samples.azw3([["<h2>Loomings</h2>", "<p>Call me Ishmael.</p>"]]),
    "combined": kindle_samples.combined("<p>Old.</p>", [["<p>New.</p>"]]),
}


def _damaged(book: bytes) -> list[bytes]:
    cut_short = [book[:length] for length in range(len(book))]
    flipped = [
        book[:at] + bytes([book[at] ^ 0xFF]) + book[at + 1 :] for at in range(len(book))
    ]
    return cut_short + flipped


@pytest.mark.parametrize("name", SAMPLES)
def test_a_damaged_book_fails_with_one_reason_never_a_crash(name: str) -> None:
    """Cut short or with any one byte flipped, a book reads or is refused as a book."""
    for book in _damaged(SAMPLES[name]):
        with suppress(KindleBookError):
            book_html(book)


def _code(entry: int) -> bytes:
    return bytes([255 - entry])


def test_a_dictionary_entry_that_contains_itself_is_damage_not_a_hang() -> None:
    """Unpacking it would unpack it again, until the nesting limit."""
    book = kindle_samples.huffcdic_book(_code(0), [(_code(0), False)])

    with pytest.raises(KindleBookError):
        book_html(book)


def test_a_dictionary_that_doubles_at_every_level_is_refused() -> None:
    """Thirty-one levels, under the nesting limit, would unpack one code to 2 GB."""
    chain = [(_code(level + 1) * 2, False) for level in range(31)]
    book = kindle_samples.huffcdic_book(_code(0), [*chain, (b"x", True)])

    with pytest.raises(KindleBookError):
        book_html(book)


def test_a_palmdoc_record_that_unpacks_far_past_its_size_is_refused() -> None:
    """A record unpacks to 4 KB; one that keeps copying could reach gigabytes."""
    copy_ten_bytes_from_one_back = b"\x80\x0f"
    record = b"a" + copy_ten_bytes_from_one_back * 10_000
    header = kindle_samples.mobi_header(
        text_length=100_001, text_records=1, compression=2
    )

    with pytest.raises(KindleBookError):
        book_html(kindle_samples.container([header, record]))


def test_a_kf8_index_that_reuses_its_text_over_and_over_is_refused() -> None:
    """Put together, a book's files are no bigger than its text; a crafted index
    listing one fragment thousands of times would make them far bigger."""
    book = kindle_samples.azw3([[CHAPTER * 20]], fragment_repeats=2_000)

    with pytest.raises(KindleBookError):
        book_html(book)


def test_a_mobi6_title_in_large_type_reads_as_a_heading() -> None:
    """MOBI 6 has no heading tags: calibre writes a title as a paragraph in a large
    font, which is what a reader sees. A big first letter is not a title."""
    html = book_html(
        kindle_samples.mobi(
            '<p align="center"><font size="7">CHAPTER I.</font><br/>'
            '<font size="7">Down the Rabbit-Hole</font></p>'
            '<p><font size="6"><b>Contents</b></font></p>'
            '<p><font size="+2">Part One</font></p>'
            '<p><font size="7">A</font>lice was beginning to get very tired.</p>'
            '<p><font size="3">Plain text.</font></p>'
        )
    )

    assert '<h1><font size="7">CHAPTER I.</font><br/>' in html
    assert '<h2><font size="6"><b>Contents</b></font></h2>' in html
    assert '<h3><font size="+2">Part One</font></h3>' in html
    assert '<p><font size="7">A</font>lice was beginning' in html
    assert '<p><font size="3">Plain text.</font></p>' in html


@pytest.mark.parametrize(
    "html",
    [
        "<p>Some words in a paragraph that never closes. " * 40_000,
        "<p>" + '<font size="7">big words never closed ' * 40_000 + "</p>",
    ],
    ids=["paragraphs", "fonts"],
)
def test_tags_left_unclosed_do_not_make_reading_slow(html: str) -> None:
    """Old Mobipocket files leave tags open; searching ahead for each one's close
    once took four minutes on a 2 MB book."""
    book = kindle_samples.mobi(html)

    started = time.monotonic()
    assert book_html(book) == html
    assert time.monotonic() - started < 5


def test_a_plain_palmdoc_text_reads_as_paragraphs_of_text() -> None:
    """Old e-texts saved as .mobi hold text, not HTML: markup in them is words."""
    html = book_html(
        kindle_samples.palmdoc_text("It was a dark night.\n\nThe <b> tag & café.")
    )

    assert "<p>It was a dark night.</p>" in html
    assert "<p>The &lt;b&gt; tag &amp; café.</p>" in html


@pytest.mark.parametrize(
    "book",
    [
        kindle_samples.mobi("<p>Locked.</p>", encryption=2),
        kindle_samples.mobi("<p>Locked.</p>", encryption=1),
        kindle_samples.palmdoc_text("Locked.", encryption=1),
        kindle_samples.combined("<p>Open.</p>", [["<p>Locked.</p>"]], kf8_encryption=2),
    ],
    ids=["mobipocket-drm", "old-mobipocket-drm", "palmdoc-drm", "kf8-copy-drm"],
)
def test_a_book_with_drm_is_refused_as_drm(book: bytes) -> None:
    """Its text records are ciphertext; read as text they would be noise."""
    with pytest.raises(DrmProtectedError):
        book_html(book)


def test_a_mobi6_book_is_split_into_its_pages() -> None:
    """MOBI 6 marks a page break, not a block: a book of entries with no <p> is one
    block of megabytes to Docling, which read a 4.5 MB dictionary in 80 s, not 6."""
    html = book_html(
        kindle_samples.mobi(
            "<html><head><guide></guide></head><body>"
            "<b>1802</b><br/> An 8-bit processor.<mbp:pagebreak/>"
            "<b>1983</b><br/> A year.<mbp:pagebreak></mbp:pagebreak>"
            "<b>2001</b><br/> Another.</body></html>"
        )
    )

    assert html == (
        "<html><head><guide></guide></head><body>"
        "<div><b>1802</b><br/> An 8-bit processor.</div>"
        "<div><b>1983</b><br/> A year.</div>"
        "<div><b>2001</b><br/> Another.</div></body></html>"
    )
