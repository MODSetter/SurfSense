import pytest
from trafilatura.utils import load_html

from modules.documents.web_sources.page_reading.lost_prices import with_prices
from modules.documents.web_sources.page_reading.page_text import page_text

pytestmark = pytest.mark.unit

URL = "https://tides.example/explained"
PARAGRAPH = (
    "The moon pulls the sea towards it, so the water rises in a bulge on the side "
    "facing it and on the far side too, and the coast sees two high tides a day."
)


def page(body: str, title: str = "Tide tables explained") -> str:
    """A whole HTML document around `body`."""
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def test_a_page_is_kept_as_its_main_text_under_its_title() -> None:
    """Navigation and footer are not the page."""
    pulled = page_text(
        page(
            "<nav><a href='/'>Home</a></nav>"
            f"<article><h1>Tide tables explained</h1>{f'<p>{PARAGRAPH}</p>' * 6}</article>"
            "<footer>Contact the harbour office.</footer>"
        ),
        URL,
    )

    assert pulled is not None
    assert pulled.title == "Tide tables explained"
    assert PARAGRAPH in pulled.markdown
    assert "harbour office" not in pulled.markdown


def test_a_heading_keeps_its_words_without_its_permalink() -> None:
    """Sphinx and MkDocs glue a pilcrow onto every heading."""
    pulled = page_text(
        page(
            "<article><h2>Spring tides"
            '<a class="headerlink" href="#spring">¶</a></h2>'
            f"{f'<p>{PARAGRAPH}</p>' * 6}</article>"
        ),
        URL,
    )

    assert pulled is not None
    assert "Spring tides" in pulled.markdown
    assert "¶" not in pulled.markdown


def test_a_bot_wall_is_no_page() -> None:
    """Its few words are Cloudflare's, not the site's."""
    wall = page(
        '<div id="challenge-running">Checking your browser before accessing '
        "tides.example. This process is automatic. Your browser will redirect to "
        "your requested content shortly. Please allow up to 5 seconds.</div>",
        title="Just a moment...",
    )

    assert page_text(wall, URL) is None


def test_a_shell_its_scripts_would_fill_is_no_page() -> None:
    """A megabyte of HTML around a paragraph: only a browser would read the rest."""
    shell = page(
        f"<main><p>{PARAGRAPH}</p><p>{PARAGRAPH}</p></main>"
        f"<script>window.__STATE__ = '{'x' * 1_100_000}'</script>"
    )

    assert page_text(shell, URL) is None


def test_a_page_with_no_text_is_no_page() -> None:
    """Nothing to keep."""
    assert page_text(page(""), URL) is None


PRICING = page(
    f"<article><h1>Plans</h1><p>{PARAGRAPH}</p></article>"
    '<div class="grid"><div class="card"><span>Team</span><span>$49</span></div>'
    '<div class="card"><span>Firm</span><span>$199</span></div></div>'
)


def test_prices_the_text_lost_are_read_from_the_whole_page() -> None:
    """A pricing grid dropped as boilerplate is the point of the page."""
    repaired = with_prices(load_html(PRICING), PRICING, URL, f"# Plans\n\n{PARAGRAPH}")

    assert "$49" in repaired
    assert "$199" in repaired


def test_text_that_kept_its_prices_is_left_as_it_is() -> None:
    """No second extraction for a page that lost nothing."""
    kept = "# Plans\n\nTeam is $49."

    assert with_prices(load_html(PRICING), PRICING, URL, kept) == kept
