"""A license file is checked out only after Keygen validates the license.

Keygen checks no license status when an admin or product token checks a file
out, so a suspended license would still get a fresh file. Every delivery,
whether success page, mail, resend or the app's refresh, comes through here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from license import keygen
from license.keygen import Validation

logger = logging.getLogger(__name__)

# EXPIRED as well: the file carries the expiry the app already shows, and a
# lapsed trial's resend has always been answered. Anything else, SUSPENDED and
# BANNED above all, gets no file.
_DELIVERABLE_CODES = frozenset({"VALID", "EXPIRED"})


def deliverable(validation: Validation) -> bool:
    return validation.code in _DELIVERABLE_CODES


async def fresh_file(license_id: str) -> str | None:
    """A new file for the license, or ``None`` when Keygen says it is not in good standing."""
    validation = await keygen.validate_license(license_id)
    if not deliverable(validation):
        logger.info(
            "Not checking out license %s: Keygen validates it as %s",
            license_id,
            validation.code or "no code",
        )
        return None
    return await keygen.checkout_license(license_id)


@dataclass(frozen=True, slots=True)
class KeyedFile:
    """What a key validates as, and its new file when it may have one."""

    code: str
    certificate: str | None = None


async def fresh_file_for_key(key: str) -> KeyedFile:
    """The same rule for a caller that holds only the key: the app, after a renewal."""
    validation = await keygen.validate_key(key)
    license_id = str((validation.record or {}).get("id") or "")
    if not license_id:
        return KeyedFile("NOT_FOUND")
    if not deliverable(validation):
        return KeyedFile(validation.code or "NOT_FOUND")
    return KeyedFile(validation.code, await keygen.checkout_license(license_id))
