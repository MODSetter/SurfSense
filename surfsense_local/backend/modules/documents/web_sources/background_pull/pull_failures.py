"""Why a pull failed, in a sentence the sources panel shows on the row."""

from modules.documents.web_sources.plugin_calls.plugin_access import (
    MISSING_LICENSE,
    LicenseRefusedError,
)
from modules.egress.service import EgressDeniedError

UNREADABLE = "This link couldn't be read."
UNREACHABLE = "SurfSense's plugins couldn't be reached. Try again later."
_LICENSE = {
    MISSING_LICENSE: "Pulling links needs a SurfSense license.",
    "expired": "Your SurfSense license has expired.",
}
_LICENSE_REFUSED = "Your SurfSense license wasn't accepted."


def license_sentence(error: LicenseRefusedError) -> str:
    return _LICENSE.get(error.reason, _LICENSE_REFUSED)


def network_sentence(error: EgressDeniedError) -> str:
    return f"Sending to {error.host} is off in Settings > Network."
