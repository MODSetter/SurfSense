"""What reaches PostHog from the licence slice, recorded instead of sent."""

from __future__ import annotations

import pytest

from license import analytics


class CapturedEvents(list):
    """Every ``capture()`` the PostHog client received, as plain dicts."""

    def capture(self, event, *, distinct_id, properties, groups, disable_geoip):
        self.append(
            {
                "event": event,
                "distinct_id": distinct_id,
                "properties": properties,
                "disable_geoip": disable_geoip,
            }
        )

    def named(self, event: str) -> list[dict]:
        return [captured for captured in self if captured["event"] == event]


@pytest.fixture
def posthog_events(monkeypatch: pytest.MonkeyPatch) -> CapturedEvents:
    events = CapturedEvents()
    monkeypatch.setattr(analytics, "_client", events)
    monkeypatch.setattr(analytics, "_init_attempted", True)
    return events
