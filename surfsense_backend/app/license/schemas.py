"""Schemas for the unauthenticated license routes."""

from pydantic import BaseModel, EmailStr


class LicenseEmailRequest(BaseModel):
    """An email address, the only input the resend and trial routes take."""

    email: EmailStr


class LicenseAckResponse(BaseModel):
    """Outcome-independent acknowledgement.

    ``/license/resend`` returns this whether or not a license was found, so the
    endpoint cannot be used to learn who is a customer. Nothing here may vary
    with the lookup result.
    """

    detail: str
