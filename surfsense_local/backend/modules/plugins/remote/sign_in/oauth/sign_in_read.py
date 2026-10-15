"""A sign-in as the screen sees it: the page to open, then whether it finished. Never a token."""

from pydantic import BaseModel

from modules.plugins.remote.sign_in.oauth.plugin_sign_ins import (
    PendingSignIn,
    SignInStatus,
)


class SignInStarted(BaseModel):
    id: str
    plugin_id: str
    authorization_url: str


class SignInRead(BaseModel):
    id: str
    plugin_id: str
    status: SignInStatus
    # Why it failed, in a sentence; None otherwise.
    message: str | None


def started(pending: PendingSignIn) -> SignInStarted:
    return SignInStarted(
        id=pending.id,
        plugin_id=pending.draft.plugin_id,
        authorization_url=pending.authorization_url,
    )


def read_sign_in(pending: PendingSignIn) -> SignInRead:
    return SignInRead(
        id=pending.id,
        plugin_id=pending.draft.plugin_id,
        status=pending.status,
        message=pending.message,
    )
