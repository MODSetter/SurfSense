import pytest

from proprietary.scraping.logged_host import logged_host


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("https://www.amazon.com/dp/B0CX23V2ZK?th=1", "www.amazon.com"),
        ("https://www.google.com/search?q=private+clinic", "www.google.com"),
        ("https://user:pass@gw.example.com:823/x", "gw.example.com"),
        ("/r/python/comments/abc", "-"),
        ("", "-"),
        (None, "-"),
        ("http://[::1", "-"),
    ],
)
def test_a_logged_url_is_only_its_host(url: str | None, shown: str) -> None:
    assert logged_host(url) == shown
