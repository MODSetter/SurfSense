from ipaddress import ip_address

from api.config import Settings


def test_default_host_is_loopback() -> None:
    """The API ships without auth, so it must never bind past this machine."""
    assert ip_address(Settings().host).is_loopback
