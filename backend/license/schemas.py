"""Schemas for the unauthenticated license routes."""

from pydantic import BaseModel, EmailStr, field_validator

from license.funnel.channel import valid_channel


class LicenseEmailRequest(BaseModel):
    """An email address, the only input the resend route takes."""

    email: EmailStr


class LicenseTrialRequest(LicenseEmailRequest):
    """A trial claim, with the site's acquisition channel when it sent one.

    ``channel`` must match ``^[a-z0-9_-]{1,40}$``. Anything else is dropped
    rather than refused: a bad tag must never cost someone their trial.
    """

    channel: str | None = None

    @field_validator("channel", mode="before")
    @classmethod
    def _keep_only_a_channel_tag(cls, value: object) -> str | None:
        return valid_channel(value)


class LicenseAckResponse(BaseModel):
    """Outcome-independent acknowledgement.

    ``/license/resend`` returns this whether or not a license was found, so the
    endpoint cannot be used to learn who is a customer. Nothing here may vary
    with the lookup result.
    """

    detail: str
