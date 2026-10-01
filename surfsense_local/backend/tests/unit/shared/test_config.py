from ipaddress import ip_address

import pytest

from api.config import Settings

pytestmark = pytest.mark.unit


def test_default_host_is_loopback() -> None:
    """The API ships without auth, so it must never bind past this machine."""
    assert ip_address(Settings().host).is_loopback


def test_cors_origins_default_allows_any() -> None:
    """The packaged renderer loads from file://, so unset keeps today's open CORS."""
    assert Settings().cors_origin_list() == ["*"]


def test_cors_origins_splits_on_commas_and_drops_blanks() -> None:
    """Operators write `a, b,` by hand; whitespace and empty items are noise."""
    settings = Settings(cors_origins=" https://a.example, https://b.example ,, ")
    assert settings.cors_origin_list() == ["https://a.example", "https://b.example"]


def test_cors_origins_empty_means_no_origin_allowed() -> None:
    """The Docker image sets it empty to switch cross-origin access off."""
    assert Settings(cors_origins="").cors_origin_list() == []
