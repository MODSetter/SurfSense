"""``EventBus`` contract: subscribe, publish (stamp + fan out), dispatch.

Each test uses a fresh ``EventBus`` — no shared global state.
"""

from __future__ import annotations

import pytest

from app.event_bus import Event, EventBus

pytestmark = pytest.mark.unit


def _event() -> Event:
    return Event(event_type="x.happened", payload={"k": "v"}, workspace_id=1)


async def _noop(_event: Event) -> None:
    return None


async def _other(_event: Event) -> None:
    return None


# --- registry -------------------------------------------------------------


def test_subscribe_then_subscribers_returns_the_handler() -> None:
    bus = EventBus()
    bus.subscribe(_noop)

    assert _noop in bus.subscribers()


def test_subscribe_is_idempotent_for_the_same_handler() -> None:
    """Registering the same handler twice must not make it fire twice."""
    bus = EventBus()
    bus.subscribe(_noop)
    bus.subscribe(_noop)

    assert bus.subscribers().count(_noop) == 1


def test_distinct_handlers_both_register() -> None:
    bus = EventBus()
    bus.subscribe(_noop)
    bus.subscribe(_other)

    registered = bus.subscribers()
    assert _noop in registered
    assert _other in registered


def test_subscribers_returns_a_defensive_snapshot() -> None:
    """Mutating the returned list must not corrupt the registry."""
    bus = EventBus()
    bus.subscribe(_noop)

    snapshot = bus.subscribers()
    snapshot.clear()

    assert _noop in bus.subscribers()


def test_subscribe_returns_handler_so_it_can_be_used_as_a_decorator() -> None:
    bus = EventBus()
    returned = bus.subscribe(_other)

    assert returned is _other


def test_two_buses_do_not_share_subscribers() -> None:
    """The registry is per-instance, not global."""
    a = EventBus()
    b = EventBus()
    a.subscribe(_noop)

    assert _noop in a.subscribers()
    assert _noop not in b.subscribers()


# --- dispatch -------------------------------------------------------------


async def test_dispatch_delivers_event_to_every_subscriber() -> None:
    bus = EventBus()
    seen: list[tuple[str, Event]] = []

    async def first(event: Event) -> None:
        seen.append(("first", event))

    async def second(event: Event) -> None:
        seen.append(("second", event))

    bus.subscribe(first)
    bus.subscribe(second)

    event = _event()
    await bus.dispatch(event)

    assert ("first", event) in seen
    assert ("second", event) in seen


async def test_dispatch_isolates_a_failing_subscriber() -> None:
    """A subscriber that raises must not stop a healthy one from running."""
    bus = EventBus()
    healthy_ran = False

    async def boom(_event: Event) -> None:
        raise RuntimeError("subscriber blew up")

    async def healthy(_event: Event) -> None:
        nonlocal healthy_ran
        healthy_ran = True

    bus.subscribe(boom)
    bus.subscribe(healthy)

    await bus.dispatch(_event())

    assert healthy_ran is True


async def test_dispatch_never_propagates_subscriber_errors() -> None:
    """``dispatch`` itself must not raise even if every subscriber fails."""
    bus = EventBus()

    async def boom(_event: Event) -> None:
        raise ValueError("nope")

    bus.subscribe(boom)

    await bus.dispatch(_event())  # must not raise


async def test_dispatch_with_no_subscribers_is_a_noop() -> None:
    bus = EventBus()
    await bus.dispatch(_event())  # must not raise


# --- publish --------------------------------------------------------------


async def test_publish_builds_a_stamped_event_and_fans_it_out() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.publish("document.indexed", {"document_id": 42}, workspace_id=7)

    assert len(received) == 1
    event = received[0]
    assert event.event_type == "document.indexed"
    assert event.payload == {"document_id": 42}
    assert event.workspace_id == 7
    # Engine-stamped identity/time on the way through.
    assert event.event_id
    assert event.occurred_at


async def test_publish_defaults_payload_to_empty_dict() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.publish("x.happened", workspace_id=1)

    assert received[0].payload == {}


async def test_publish_with_no_subscribers_is_a_noop() -> None:
    await EventBus().publish("x.happened", workspace_id=1)  # must not raise
