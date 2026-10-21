"""The submitted icon is fetched only over https from a public host, and never past 32 KB."""

import anyio
import pytest

from registry_check.submission.icon_fetch import IconRefusedError, fetch_icon


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("http://acme.example/icon.svg", "must be an https link"),
        ("https://127.0.0.1/icon.svg", "must be on a public host"),
        ("https://169.254.169.254/latest", "must be on a public host"),
        ("https://localhost/icon.svg", "must be on a public host"),
    ],
)
def test_an_address_the_runner_must_not_reach_is_refused(address, reason):
    with pytest.raises(IconRefusedError, match=reason):
        anyio.run(fetch_icon, address)


def test_a_host_that_cannot_be_reached_is_a_reason_not_a_crash():
    # .invalid never resolves (RFC 2606).
    with pytest.raises(IconRefusedError, match="could not be reached"):
        anyio.run(fetch_icon, "https://icons.invalid/acme.svg")
