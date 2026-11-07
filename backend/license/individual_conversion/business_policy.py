"""The Business policy a conversion moves licenses to, checked before anything is written.

Keygen refuses a move between policies that differ in encryption, pooling or
scheme, or to a stricter machine or component uniqueness (keygen-api v1.7.2,
``license.rb``), and ``RESET_EXPIRY`` gives each license moved a new expiry.
Keygen checks the component's only when the machine's are equal; this checks
both, so it may refuse a pair Keygen would take, never the reverse. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from license import keygen
from license.scripts.setup_business_policies import MARKER

# keygen-api v1.7.2 ``policy.rb``; a strategy it does not know ranks -1.
_UNIQUENESS_RANKS = {
    "UNIQUE_PER_ACCOUNT": 4,
    "UNIQUE_PER_PRODUCT": 3,
    "UNIQUE_PER_POLICY": 2,
    "UNIQUE_PER_LICENSE": 1,
    "UNIQUE_PER_MACHINE": 0,
}
_SAME_ON_BOTH = ("encrypted", "usePool", "scheme")
_NO_STRICTER = ("machineUniquenessStrategy", "componentUniquenessStrategy")


class PolicyMismatchError(RuntimeError):
    """The policies cannot take the conversion; nothing has been written."""


@dataclass(frozen=True, slots=True)
class BusinessPolicy:
    id: str
    name: str


async def checked_business_policy(*, individual: str, business: str) -> BusinessPolicy:
    """Raises ``PolicyMismatchError`` naming what is wrong; Keygen's own errors propagate."""
    target = await _attributes(business, "KEYGEN_POLICY_BUSINESS")
    source = await _attributes(individual, "KEYGEN_POLICY_INDIVIDUAL")
    name = str(target.get("name") or business)

    marker = (target.get("metadata") or {}).get(MARKER)
    if marker != "business":
        raise PolicyMismatchError(
            f"KEYGEN_POLICY_BUSINESS names {name}, whose {MARKER} is "
            f"{marker or 'unset'}, not the Business policy "
            "scripts/setup_business_policies.py creates"
        )
    for attribute in _SAME_ON_BOTH:
        if target.get(attribute) != source.get(attribute):
            raise PolicyMismatchError(
                f"The Business policy's {attribute} is {target.get(attribute)} and the "
                f"Individual policy's {source.get(attribute)}, so Keygen would refuse "
                "to move any license"
            )
    for attribute in _NO_STRICTER:
        if _rank(target.get(attribute)) > _rank(source.get(attribute)):
            raise PolicyMismatchError(
                f"The Business policy's {attribute}, {target.get(attribute)}, is "
                f"stricter than the Individual policy's, {source.get(attribute)}, so "
                "Keygen would refuse to move any license"
            )
    strategy = target.get("transferStrategy")
    if strategy != "KEEP_EXPIRY":
        raise PolicyMismatchError(
            f"The Business policy's transferStrategy is {strategy or 'unset'}, so each "
            "move would give a license a new expiry; set it to KEEP_EXPIRY in Keygen"
        )
    return BusinessPolicy(business, name)


async def _attributes(policy_id: str, setting: str) -> dict[str, Any]:
    response = await keygen.account_request("GET", f"policies/{policy_id}")
    if response.status_code == 404:
        raise PolicyMismatchError(
            f"{setting} names a policy Keygen does not show this token: none, or "
            "another product's"
        )
    response.raise_for_status()
    data = response.json().get("data")
    attributes = data.get("attributes") if isinstance(data, dict) else None
    return attributes if isinstance(attributes, dict) else {}


def _rank(strategy: Any) -> int:
    return _UNIQUENESS_RANKS.get(str(strategy or ""), -1)
