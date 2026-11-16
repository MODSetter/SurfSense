"""The installers licence mail links to: the site's counting redirect, pinned to a tag."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from license.release import APP_RELEASE_TAG, installer_link, installer_links

pytestmark = pytest.mark.unit


def test_every_platform_is_offered_in_the_grid_order():
    assert [link.label for link in installer_links()] == [
        "Windows (exe)",
        "macOS Apple Silicon (dmg)",
        "Linux (deb)",
        "Linux (AppImage)",
    ]


def test_each_link_is_the_site_redirect_for_its_platform():
    paths = [urlsplit(link.url).path for link in installer_links()]

    assert paths == [
        "/downloads/windows",
        "/downloads/mac",
        "/downloads/linux-deb",
        "/downloads/linux-appimage",
    ]
    for link in installer_links():
        assert link.url.startswith("https://www.surfsense.com/downloads/")


def test_a_sent_mail_stays_pinned_to_its_build_and_says_it_came_from_mail():
    """``v`` keeps an old mail on its release; the redirect would otherwise use today's pin."""
    for link in installer_links():
        query = parse_qs(urlsplit(link.url).query)
        assert query == {"src": ["email"], "v": [APP_RELEASE_TAG]}


def test_links_never_point_at_a_moving_target():
    for link in installer_links():
        assert "github.com" not in link.url
        assert "latest" not in link.url


def test_a_tag_can_be_named_explicitly():
    url = installer_link("windows", tag="v2.0.2")

    assert url == "https://www.surfsense.com/downloads/windows?src=email&v=v2.0.2"
