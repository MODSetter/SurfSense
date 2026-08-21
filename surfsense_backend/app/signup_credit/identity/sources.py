"""Identity sources, one per login method."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .registry import identity_source

GOOGLE_SUBJECT = "google_subject"


@identity_source(GOOGLE_SUBJECT)
def google_subject_ids(user: Any) -> Iterator[str]:
    """Google's subject id, which survives the user renaming their email."""
    # Unmapped under AUTH_TYPE=LOCAL, so absence is normal rather than an error.
    for account in getattr(user, "oauth_accounts", None) or ():
        if getattr(account, "oauth_name", None) != "google":
            continue

        # Rows predating the `sub` switch stored `people/<sub>`; migration 169
        # deliberately left some of them in place.
        subject = (account.account_id or "").removeprefix("people/")
        if subject:
            yield subject
