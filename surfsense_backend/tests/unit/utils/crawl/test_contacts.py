"""``extract_contacts`` behavior: harvest emails/phones/socials from raw HTML."""

from __future__ import annotations

import pytest

from app.utils.crawl import extract_contacts

pytestmark = pytest.mark.unit


def test_harvests_mailto_tel_and_socials() -> None:
    html = """
    <html><body>
      <footer>
        <a href="mailto:hello@acme.io?subject=hi">Email us</a>
        <a href="tel:+1-555-0100">Call</a>
        <a href="https://www.linkedin.com/company/acme">LinkedIn</a>
        <a href="https://x.com/acme">X</a>
        <a href="https://github.com/acme/repo#readme">GitHub</a>
        <a href="https://acme.io/about">About</a>
      </footer>
    </body></html>
    """
    c = extract_contacts(html)
    assert c.emails == ["hello@acme.io"]  # mailto query stripped
    assert c.phones == ["+1-555-0100"]
    assert c.socials == [
        "https://www.linkedin.com/company/acme",
        "https://x.com/acme",
        "https://github.com/acme/repo",  # fragment stripped
    ]
    # Same-site, non-social link is not a contact signal.
    assert "https://acme.io/about" not in c.socials


def test_plaintext_email_without_mailto_is_found() -> None:
    html = "<html><body><p>Reach us at hello@cochat.ai for support.</p></body></html>"
    assert extract_contacts(html).emails == ["hello@cochat.ai"]


def test_filters_noise_emails_and_asset_false_positives() -> None:
    html = """
    <html><body>
      <img src="logo@2x.png">
      <script src="react@18.2.0.js"></script>
      <p>ops@sentry.io</p>
      <a href="mailto:real@company.com">x</a>
    </body></html>
    """
    assert extract_contacts(html).emails == ["real@company.com"]


def test_filters_template_placeholders() -> None:
    html = """
    <html><body>
      <p>youremail@business.com your.email@acme.io john-doe@acme.io</p>
      <a href="mailto:hello@acme.io">real</a>
      <a href="https://github.com/username">gh template</a>
      <a href="https://twitter.com/your-handle">tw template</a>
      <a href="https://www.linkedin.com/in/jane-doe/">real person</a>
    </body></html>
    """
    c = extract_contacts(html)
    assert c.emails == ["hello@acme.io"]  # your.email + john-doe normalized away
    assert c.socials == ["https://www.linkedin.com/in/jane-doe/"]


def test_regional_social_hosts_are_harvested() -> None:
    """WhatsApp/Line/VK/Weibo etc. are the business contact channel outside the US."""
    html = """
    <a href="https://wa.me/5511999999999">WhatsApp</a>
    <a href="https://line.me/R/ti/p/@acme">Line</a>
    <a href="https://vk.com/acme">VK</a>
    <a href="https://weibo.com/acme">Weibo</a>
    <a href="https://www.xing.com/pages/acme">Xing</a>
    """
    assert len(extract_contacts(html).socials) == 5


def test_percent_encoded_hrefs_are_decoded() -> None:
    """Sites URL-encode tel/mailto hrefs (seen live: tel:+1%20408-629-1770)."""
    html = """
    <a href="tel:+1%20408-629-1770">Call</a>
    <a href="mailto:hello%40acme.io">Email</a>
    """
    c = extract_contacts(html)
    assert c.phones == ["+1 408-629-1770"]
    assert "hello@acme.io" in c.emails


def test_dedupes_case_insensitively_preserving_order() -> None:
    html = """
    <a href="mailto:Hello@Acme.io">a</a>
    <a href="mailto:hello@acme.io">b</a>
    """
    assert extract_contacts(html).emails == ["Hello@Acme.io"]


def test_empty_or_unparseable_html_is_empty() -> None:
    assert extract_contacts("").is_empty
    assert extract_contacts(None).is_empty
    assert extract_contacts("   ").is_empty
