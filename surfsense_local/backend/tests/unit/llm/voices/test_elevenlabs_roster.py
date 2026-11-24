"""An account's voices, and what is kept through a failure to read them."""

import httpx
import pytest

from modules.llm.voices import elevenlabs_roster
from modules.llm.voices.elevenlabs_roster import elevenlabs_voices
from modules.llm.voices.voice import Voice

pytestmark = pytest.mark.unit

GEORGE = Voice("george", "George", "male", ())


def test_a_new_key_is_not_answered_with_the_old_accounts_voices(monkeypatch) -> None:
    """An edit keeps the connection, its address and its model, but not the account."""

    def reads(base_url, api_key, model):
        if api_key == "old":
            return [GEORGE]
        raise httpx.ConnectError("down")

    monkeypatch.setattr(elevenlabs_roster, "voices_for_model", reads)

    assert elevenlabs_voices(11, "http://x", "old", "m").voices == [GEORGE]
    read = elevenlabs_voices(11, "http://x", "new", "m")

    assert read.voices == []
    assert read.problem is not None


def test_the_same_key_keeps_its_voices_through_an_outage(monkeypatch) -> None:
    """One failed request at Generate should not refuse a good brief."""
    answers = [[GEORGE]]

    def reads(base_url, api_key, model):
        if answers:
            return answers.pop()
        raise httpx.ConnectError("down")

    monkeypatch.setattr(elevenlabs_roster, "voices_for_model", reads)

    elevenlabs_voices(12, "http://x", "k", "m")
    assert elevenlabs_voices(12, "http://x", "k", "m").voices == [GEORGE]


def test_no_key_is_kept_in_what_is_held(monkeypatch) -> None:
    """The held voices outlive the request, and the key is only needed to tell them apart."""
    monkeypatch.setattr(elevenlabs_roster, "voices_for_model", lambda *_: [GEORGE])

    elevenlabs_voices(13, "http://x", "a-secret-key", "m")

    assert "a-secret-key" not in repr(elevenlabs_roster._held)
