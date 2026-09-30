"""Support finds the trial behind a mistyped address, and only that one.

A trial has no payment to prove, so the anchor is the exact address the trial
was issued to. The lookup must not match on a lookalike, and must refuse rather
than choose when two licences answer.
"""

from __future__ import annotations

import pytest

from app.license import keygen
from app.license.models import META_EMAIL, META_TRIAL_KEY, LicenseNotFoundError
from app.license.records import find_trial_license_by_email

pytestmark = pytest.mark.unit


def trial(license_id: str, email: str, trial_key: str) -> dict:
    """A trial licence as Keygen lists it."""
    return {
        "id": license_id,
        "attributes": {
            "metadata": {META_EMAIL: email, META_TRIAL_KEY: trial_key},
            "maxUsers": None,
            "expiry": "2026-10-14T00:00:00Z",
        },
    }


@pytest.fixture
def keygen_answers(monkeypatch):
    """Keygen's list endpoint, answering with the licences a test sets."""
    seen: list[dict] = []
    answer: list[dict] = []

    async def list_licenses(*, metadata=None, limit=100, **_):
        seen.append(dict(metadata or {}))
        return answer[:limit]

    monkeypatch.setattr(keygen, "list_licenses", list_licenses)
    return seen, answer


async def test_a_trial_is_found_by_the_exact_address_it_was_issued_to(keygen_answers):
    """Filtered on the typed address and its trial key, so a paid licence never matches."""
    seen, answer = keygen_answers
    answer.append(trial("lic-1", "typo+work@example.test", "typo@example.test"))

    record = await find_trial_license_by_email("  Typo+Work@Example.test ")

    assert record.keygen_license_id == "lic-1"
    assert record.metadata[META_EMAIL] == "typo+work@example.test"
    assert seen == [
        {META_EMAIL: "typo+work@example.test", META_TRIAL_KEY: "typo@example.test"}
    ]


async def test_two_trials_on_one_address_are_refused(keygen_answers):
    """Picking one would be a guess about whose trial it is."""
    _, answer = keygen_answers
    answer += [
        trial("lic-1", "typo@example.test", "typo@example.test"),
        trial("lic-2", "typo@example.test", "typo@example.test"),
    ]

    with pytest.raises(LicenseNotFoundError, match="2 trial licenses"):
        await find_trial_license_by_email("typo@example.test")


async def test_an_address_no_trial_was_issued_to_is_not_found(keygen_answers):
    """A lookalike is not a match; support asks again rather than guessing."""
    with pytest.raises(LicenseNotFoundError, match="No trial license"):
        await find_trial_license_by_email("nobody@example.test")
