from typing import Literal

from pydantic import BaseModel

OfficeState = Literal[
    "not_installed",
    "downloading",
    "unpacking",
    "checking",
    "installed",
    "using_installed",
    "error",
]


class OfficeProgress(BaseModel):
    completed: int
    total: int


class OfficeProblem(BaseModel):
    """`code` keys the interface's message; `message` is for logs, in English."""

    code: str
    message: str


class OfficeOffer(BaseModel):
    """What turning Office support on downloads on this machine."""

    version: str
    size: int
    host: str
    # The egress destination the download needs allowed.
    destination: str


class OfficeDetected(BaseModel):
    """A LibreOffice at a fixed install path; `refusal` says why it cannot be used."""

    path: str
    branch: str | None
    usable: bool
    refusal: str | None


class OfficeStatusRead(BaseModel):
    state: OfficeState
    # The pack's version, or the confirmed LibreOffice's.
    version: str | None
    # The confirmed LibreOffice's install folder, when that is what runs.
    path: str | None
    progress: OfficeProgress | None
    error: OfficeProblem | None
    # None where nothing is pinned for this platform.
    offer: OfficeOffer | None
    detected: OfficeDetected | None
    # The thread's banner offers Office support only until this is true.
    offer_dismissed: bool
