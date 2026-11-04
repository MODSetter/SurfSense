from collections.abc import Iterator

import pytest

from shared.config import get_license_server_settings
from tests.license_server_stand_in import StandInLicenseServer
from tests.mcp_test_server import serving


@pytest.fixture
def license_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[StandInLicenseServer]:
    """SurfSense's license server run locally, as a developer's build points at it."""
    stand_in = StandInLicenseServer()
    with serving(stand_in.app()) as base:
        monkeypatch.setattr(get_license_server_settings(), "license_server_url", base)
        yield stand_in


@pytest.fixture
def compiled_license_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The build's own server, api.surfsense.com, whatever this machine's environment says."""
    monkeypatch.setattr(get_license_server_settings(), "license_server_url", None)
