"""Offline checks for the /sorry reCAPTCHA solver's pure helpers.

The network solve can't be unit-tested, but the parsing around it can: a missed
sitekey/data-s silently burns paid solves, so these guard the boundary logic.
(Proxy reformatting lives in ``proprietary.scraping.captcha.solvers``.)
"""

from proprietary.google_search import captcha


class _Page:
    def __init__(self, url: str) -> None:
        self.url = url


def test_on_sorry_detects_wall_only():
    assert captcha.on_sorry(_Page("https://www.google.com/sorry/index?continue=x"))
    assert not captcha.on_sorry(_Page("https://www.google.com/search?q=notebooklm"))
    assert not captcha.on_sorry(_Page(""))


def test_on_sorry_reads_the_host_and_path_not_the_query():
    """A Google Search URL is rendered as given, so its query may say "/sorry/"."""
    assert captcha.on_sorry(_Page("https://www.google.co.uk/sorry/index?continue=x"))
    assert captcha.on_sorry(_Page("https://ipv4.google.com/sorry/index?continue=x"))
    assert not captcha.on_sorry(_Page("https://www.google.com/search?q=inurl:/sorry/"))
    assert not captcha.on_sorry(_Page("https://example.com/sorry/"))


def test_sitekey_and_data_s_extraction():
    html = (
        '<div class="g-recaptcha" data-sitekey="6LdLLIMbAAAAAIl-KLj9p1ePhM"'
        ' data-s="zBB1ixry9YzY_tok-en"></div>'
    )
    assert captcha._SITEKEY_RE.search(html).group(1) == "6LdLLIMbAAAAAIl-KLj9p1ePhM"
    assert captcha._DATA_S_RE.search(html).group(1) == "zBB1ixry9YzY_tok-en"


def test_latch_roundtrip():
    captcha.reset_solver_latch()
    assert not captcha.solver_latched()
    captcha._latch("no balance")
    assert captcha.solver_latched()
    captcha.reset_solver_latch()
    assert not captcha.solver_latched()
