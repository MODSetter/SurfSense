"""Stripe faked at its HTTP transport, and events signed as Stripe signs them.

The real ``StripeClient`` runs over this, so the code under test reads Stripe's
objects as the SDK hands them over, not as a test author imagined them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from stripe import HTTPClient, StripeClient

SECRET = "whsec_test"


def signed(payload: bytes, secret: str = SECRET) -> dict[str, str]:
    """Stripe's scheme: an HMAC-SHA256 of `<timestamp>.<payload>` under the endpoint's secret."""
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}"}


def event(kind: str, obj: dict[str, Any], *, event_id: str = "evt_test") -> bytes:
    return json.dumps(
        {"id": event_id, "object": "event", "type": kind, "data": {"object": obj}}
    ).encode()


def stripe_list(data: list[dict[str, Any]], url: str = "/v1/list") -> dict[str, Any]:
    return {"object": "list", "data": data, "has_more": False, "url": url}


def subscription(
    subscription_id: str, *, period_end: int, quantity: int = 1, price: str = "price"
) -> dict[str, Any]:
    """A subscription as API 2025-03-31 and later shape it: the period on its item."""
    return {
        "id": subscription_id,
        "object": "subscription",
        "status": "active",
        "items": stripe_list(
            [
                {
                    "id": f"si_{subscription_id}",
                    "object": "subscription_item",
                    "quantity": quantity,
                    "current_period_end": period_end,
                    "price": {"id": price, "object": "price"},
                }
            ]
        ),
    }


def invoice(
    invoice_id: str, subscription_id: str | None, *, reason: str
) -> dict[str, Any]:
    parent = (
        {
            "type": "subscription_details",
            "subscription_details": {"subscription": subscription_id},
        }
        if subscription_id
        else None
    )
    return {
        "id": invoice_id,
        "object": "invoice",
        "billing_reason": reason,
        "parent": parent,
        "status": "paid",
    }


class FakeStripe(HTTPClient):
    """The Stripe endpoints the license server calls, over in-memory objects."""

    name = "fake-stripe"

    def __init__(self) -> None:
        super().__init__()
        self.sessions: dict[str, dict[str, Any]] = {}
        self.line_items: dict[str, list[dict[str, Any]]] = {}
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.invoices: dict[str, dict[str, Any]] = {}
        # payment intent -> the invoice it paid
        self.invoice_paid_by: dict[str, str] = {}
        self.charges: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []

    def client(self) -> StripeClient:
        return StripeClient("sk_test_fake", http_client=self)

    def request(self, method, url, headers, post_data=None, *, _usage=None):
        parts = urlsplit(url)
        path, query = parts.path, parse_qs(parts.query)
        self.calls.append((method.upper(), path))
        status, body = self._answer(method.upper(), path, query)
        return json.dumps(body), status, {}

    def close(self) -> None:
        pass

    def _answer(self, method: str, path: str, query: dict[str, list[str]]):
        expand = [
            v for k, values in query.items() if k.startswith("expand") for v in values
        ]
        segments = path.strip("/").split("/")[1:]
        if segments[:2] == ["checkout", "sessions"] and len(segments) == 3:
            session = self.sessions.get(segments[2])
            if session is None:
                return 404, _missing()
            if "line_items" in expand:
                session = {
                    **session,
                    "line_items": stripe_list(self.line_items.get(segments[2], [])),
                }
            return 200, session
        if segments[:2] == ["checkout", "sessions"]:
            found = [
                session
                for session in self.sessions.values()
                if all(
                    session.get(field) == values[0]
                    for field, values in query.items()
                    if field in {"payment_intent", "subscription"}
                )
            ]
            return 200, stripe_list(found[:1], "/v1/checkout/sessions")
        if segments[0] == "subscriptions" and len(segments) == 2:
            found = self.subscriptions.get(segments[1])
            return (200, found) if found else (404, _missing())
        if segments[0] == "invoice_payments":
            by_intent = (query.get("payment[payment_intent]") or [""])[0]
            of_invoice = (query.get("invoice") or [""])[0]
            payments = [
                {
                    "id": f"inpay_{intent}",
                    "object": "invoice_payment",
                    "invoice": (
                        self.invoices[invoice_id]
                        if "data.invoice" in expand
                        else invoice_id
                    ),
                    "status": "paid",
                    "payment": {"type": "payment_intent", "payment_intent": intent},
                }
                for intent, invoice_id in self.invoice_paid_by.items()
                if (by_intent and intent == by_intent)
                or (of_invoice and invoice_id == of_invoice)
            ]
            return 200, stripe_list(payments, "/v1/invoice_payments")
        if segments == ["invoices"]:
            # Newest first, as Stripe lists them.
            found = [
                held
                for held in reversed(self.invoices.values())
                if all(
                    _invoice_field(held, field) == values[0]
                    for field, values in query.items()
                    if field in {"subscription", "status"}
                )
            ]
            return 200, stripe_list(found, "/v1/invoices")
        if segments[0] == "invoices" and len(segments) == 2:
            found = self.invoices.get(segments[1])
            return (200, found) if found else (404, _missing())
        if segments == ["charges"]:
            found = [
                charge
                for charge in self.charges.values()
                if all(
                    charge.get(field) == values[0]
                    for field, values in query.items()
                    if field == "payment_intent"
                )
            ]
            return 200, stripe_list(found, "/v1/charges")
        if segments[0] == "charges" and len(segments) == 2:
            found = self.charges.get(segments[1])
            return (200, found) if found else (404, _missing())
        if segments[0] == "customers" and method == "POST":
            return 200, {"id": segments[1], "object": "customer"}
        return 404, _missing()


def _invoice_field(held: dict[str, Any], field: str) -> Any:
    """An invoice's status, or the subscription it bills, under ``parent`` as since API 2025-03-31."""
    if field == "subscription":
        details = (held.get("parent") or {}).get("subscription_details") or {}
        return details.get("subscription")
    return held.get(field)


def _missing() -> dict[str, Any]:
    return {"error": {"type": "invalid_request_error", "message": "No such object"}}
