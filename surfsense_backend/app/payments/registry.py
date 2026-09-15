"""Where handlers lay claim to slices of the Stripe webhook.

Payments owns the endpoint. Anything else that needs an event registers here,
so payments never imports its callers.

Handlers are all called ``handler(obj, db_session=..., stripe_client=...)``
and return a ``StripeWebhookResponse``; ``obj`` is the event's data object.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from stripe import StripeClient

from .schemas import StripeWebhookResponse

Handler = Callable[..., Awaitable[StripeWebhookResponse]]
Claim = Callable[[dict[str, str], Any, StripeClient], bool]


@dataclass(frozen=True)
class _Claimant:
    name: str
    claim: Claim
    handler: Handler


_event_handlers: dict[str, Handler] = {}
_claimants: list[_Claimant] = []
_fallback: _Claimant | None = None


def on_event(event_type: str, handler: Handler) -> None:
    """Take one Stripe event type outright."""
    _event_handlers[event_type] = handler


def claims_checkout(name: str, claim: Claim, handler: Handler) -> None:
    """Take the paid checkout sessions ``claim`` recognises.

    Claims must be mutually exclusive, because registration order is not a
    tiebreaker: the first match wins and nothing warns you about the second.
    Keep them keyed on facts that cannot co-occur -- an explicit
    ``purchase_type``, a session mode -- and leave "everything else" to
    ``falls_back_to`` rather than writing a claim that defaults to true.
    """
    _claimants.append(_Claimant(name=name, claim=claim, handler=handler))


def falls_back_to(handler: Handler, *, name: str) -> None:
    """Take the paid checkout sessions nobody claimed. At most one may."""
    global _fallback
    if _fallback is not None:
        raise RuntimeError(
            f"Checkout fallback already registered by {_fallback.name!r}; "
            f"{name!r} cannot take it too."
        )
    _fallback = _Claimant(name=name, claim=lambda *_: True, handler=handler)


def event_handler(event_type: str) -> Handler | None:
    return _event_handlers.get(event_type)


def checkout_handler(
    metadata: dict[str, str],
    checkout_session: Any,
    stripe_client: StripeClient,
) -> Handler | None:
    """The handler for a paid checkout session, or None if nothing takes it."""
    for claimant in _claimants:
        if claimant.claim(metadata, checkout_session, stripe_client):
            return claimant.handler
    return _fallback.handler if _fallback else None
