"""Email normalization and the disposable-domain blocklist for license routes.

Delivery and dedupe deliberately use different forms of the same address.
"""

from __future__ import annotations

import contextlib

import disposable_email_domains

from app.config import config

# github.com/disposable-email-domains, pinned in uv.lock, plus the three from
# our earlier hand-kept list that it does not carry. Extend per deployment with
# LICENSE_DISPOSABLE_EMAIL_DOMAINS rather than editing this.
_BUILTIN_DISPOSABLE_DOMAINS = frozenset(disposable_email_domains.blocklist) | {
    "33mail.com",
    "burnermail.io",
    "tempmail.com",
}


def normalize_email(email: str) -> str:
    """The address we deliver to: trimmed and lowercased, otherwise untouched.

    ``user+surfsense@gmail.com`` is a real, deliverable address the buyer may
    have chosen on purpose, so delivery must not fold it.
    """
    return email.strip().lower()


def fold_email(email: str) -> str:
    """The address we deduplicate on: normalized, with any ``+tag`` stripped.

    Plus-tagging is the cheapest possible trial farm, so the trial check folds
    it. Dots are **not** folded: that is Gmail-specific behaviour and applying
    it everywhere would wrongly collide distinct addresses at other providers.
    """
    normalized = normalize_email(email)
    local, separator, domain = normalized.partition("@")
    if not separator:
        return normalized
    local = local.split("+", 1)[0]
    return f"{local}@{domain}"


def _configured_disposable_domains() -> frozenset[str]:
    """Whatever the deployment added in LICENSE_DISPOSABLE_EMAIL_DOMAINS."""
    return frozenset(
        domain.strip().lower()
        for domain in config.LICENSE_DISPOSABLE_EMAIL_DOMAINS.split(",")
        if domain.strip()
    )


def is_disposable(email: str) -> bool:
    """Whether the address's domain, or any domain above it, is on the blocklist."""
    _, separator, domain = normalize_email(email).partition("@")
    if not separator:
        return False
    # The list is written in punycode, and `EmailStr` hands over Unicode. A
    # domain the stdlib's stricter IDNA 2003 codec refuses is checked as typed.
    with contextlib.suppress(UnicodeError):
        domain = domain.encode("idna").decode("ascii")
    labels = domain.split(".")
    # Every parent too: the list names registrable domains, and a service can
    # mint any subdomain under one. The bare TLD is never checked.
    candidates = (".".join(labels[i:]) for i in range(len(labels) - 1))
    # Two lookups, not a union: that would copy ~9k domains on every request.
    configured = _configured_disposable_domains()
    return any(
        candidate in _BUILTIN_DISPOSABLE_DOMAINS or candidate in configured
        for candidate in candidates
    )
