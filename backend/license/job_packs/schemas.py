"""What the app sends for a job pack: contract 6's request, checked before anything else."""

from typing import Annotated

from pydantic import Field, StringConstraints

from license.schemas import LicenseRefreshRequest

# A runner and its version, such as workbook-rows/1: a new version is a new runner.
RUNNER_PATTERN = r"^[a-z][a-z0-9-]{0,63}/[1-9][0-9]{0,5}$"
Runner = Annotated[str, StringConstraints(pattern=RUNNER_PATTERN)]
# A pack's version, 1 to 9 digits a part, each 0 to 9: \d takes any script's digits,
# and the version goes out in the answer's headers, which carry none of them.
VERSION_PATTERN = r"^[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}$"
Version = Annotated[str, StringConstraints(pattern=VERSION_PATTERN)]


class JobPackRequest(LicenseRefreshRequest):
    """The license's key, one job of its license, the version installed, and every runner the app ships.

    A field the server does not know is ignored, so a later app may add one.
    """

    entitlement: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
    installed_version: Version | None = None
    runners: Annotated[list[Runner], Field(min_length=1, max_length=16)]
