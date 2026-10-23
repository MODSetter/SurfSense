"""The acquisition channel tag a trial request or checkout carries.

A channel names where a visitor came from (a referral code, a utm_source, a
referring domain, or ``direct``), never a person. The site builds it; this
module only refuses or reduces anything that does not look like one.
"""

from __future__ import annotations

import re

CHANNEL_PATTERN = r"^[a-z0-9_-]{1,40}$"
_CHANNEL = re.compile(CHANNEL_PATTERN)
_OUTSIDE_ALPHABET = re.compile(r"[^a-z0-9_-]+")
_MAX_LENGTH = 40

# Recorded when a request carried no usable channel, so it stays countable
# apart from visitors the site tagged ``direct``.
UNKNOWN_CHANNEL = "unknown"


def valid_channel(value: object) -> str | None:
    """The value when it already is a channel tag, else ``None``."""
    if isinstance(value, str) and _CHANNEL.fullmatch(value):
        return value
    return None


def channel_from_reference(client_reference_id: object) -> str | None:
    """A channel from Stripe's ``client_reference_id``, reduced to the tag alphabet.

    Anyone can edit a Payment Link's query string, so the value is reduced
    rather than trusted: lowercased, other characters folded to ``-``, cut to
    40 characters.
    """
    if not isinstance(client_reference_id, str):
        return None
    tag = _OUTSIDE_ALPHABET.sub("-", client_reference_id.strip().lower())
    tag = tag.lstrip("-")[:_MAX_LENGTH].rstrip("-")
    return tag or None
