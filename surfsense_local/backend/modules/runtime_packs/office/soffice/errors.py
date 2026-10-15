"""Why a LibreOffice run produced nothing. Each code is what a caller's report names."""


class OfficeError(Exception):
    code = "office_failed"


class OfficeMissing(OfficeError):  # noqa: N818 -- the names callers report
    """No Office pack and no confirmed LibreOffice; `reason` is office_runtime()'s."""

    code = "office_missing"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Office support is not available ({reason})")


class OfficeBusy(OfficeError):  # noqa: N818 -- the names callers report
    """Another LibreOffice run held the app-wide lock until the deadline drew near."""

    code = "office_busy"


class OfficeTimeout(OfficeError):  # noqa: N818 -- the names callers report
    """The run was killed, with every process it started, at its time limit."""

    code = "office_timeout"


class OfficeFailed(OfficeError):  # noqa: N818 -- the names callers report
    """LibreOffice ended without a usable file; the message carries its last words."""

    code = "office_failed"
