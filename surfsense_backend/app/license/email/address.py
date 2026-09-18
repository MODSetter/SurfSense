"""Email normalization and the disposable-domain blocklist for license routes.

Delivery and dedupe deliberately use different forms of the same address.
"""

from __future__ import annotations

from app.config import config

# Small, deliberately conservative built-in list. Extend per deployment with
# LICENSE_DISPOSABLE_EMAIL_DOMAINS rather than editing this.
_BUILTIN_DISPOSABLE_DOMAINS = frozenset(
    {
        "0-mail.com",
        "10minutemail.com",
        "20minutemail.com",
        "33mail.com",
        "burnermail.io",
        "dispostable.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "mailinator.com",
        "maildrop.cc",
        "mailnesia.com",
        "mintemail.com",
        "mohmal.com",
        "sharklasers.com",
        "temp-mail.org",
        "tempmail.com",
        "tempmailo.com",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
    }
)


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


def disposable_domains() -> frozenset[str]:
    """Built-in blocklist plus whatever the deployment configured."""
    configured = {
        domain.strip().lower()
        for domain in config.LICENSE_DISPOSABLE_EMAIL_DOMAINS.split(",")
        if domain.strip()
    }
    return _BUILTIN_DISPOSABLE_DOMAINS | configured


def is_disposable(email: str) -> bool:
    """Whether the address's domain is on the blocklist."""
    _, separator, domain = normalize_email(email).partition("@")
    if not separator:
        return False
    return domain in disposable_domains()
