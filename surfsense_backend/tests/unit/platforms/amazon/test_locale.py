from __future__ import annotations

from app.proprietary.platforms.amazon.locale import (
    accept_language_for,
    proxy_country_for,
)


def test_proxy_country_for_confirmed_marketplaces():
    assert proxy_country_for("com") == "us"
    assert proxy_country_for("co.uk") == "gb"
    assert proxy_country_for("de") == "de"
    assert proxy_country_for("fr") == "fr"
    assert proxy_country_for("it") == "it"
    assert proxy_country_for("es") == "es"


def test_proxy_country_for_unknown_marketplace_falls_back():
    assert proxy_country_for("co.jp") is None
    assert proxy_country_for(None) is None


def test_accept_language_for_marketplaces():
    assert accept_language_for("co.uk") == "en-GB"
    assert accept_language_for("de") == "de-DE"
    assert accept_language_for("fr") == "fr-FR"
    assert accept_language_for("it") == "it-IT"
    assert accept_language_for("es") == "es-ES"


def test_accept_language_for_unknown_marketplace_defaults_to_us_english():
    assert accept_language_for("co.jp") == "en-US"
    assert accept_language_for(None) == "en-US"
