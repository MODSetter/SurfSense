"""Support finds the trial behind a mistyped address, and only that one.

A trial has no payment to prove, so the anchor is the exact address the trial
was issued to. The lookup must not match on a lookalike, and must refuse rather
than choose when two licences answer.
"""

from __future__ import annotations

import sys

import pytest

from license import keygen
from license.models import META_EMAIL, META_TRIAL_KEY, LicenseNotFoundError
from license.records import find_trial_license_by_email
from license.scripts import correct_license_email as script
from license.settings import config

pytestmark = pytest.mark.unit


def trial(
    license_id: str, email: str, trial_key: str, policy: str = "policy-trial"
) -> dict:
    """A trial licence as Keygen lists it, with the policy it was issued on."""
    return {
        "id": license_id,
        "attributes": {
            "metadata": {META_EMAIL: email, META_TRIAL_KEY: trial_key},
            "maxUsers": None,
            "expiry": "2026-10-14T00:00:00Z",
        },
        "policy": policy,
    }


@pytest.fixture
def keygen_answers(monkeypatch):
    """Keygen's list endpoint, answering with the licences a test sets, on the policy asked."""
    seen: list[tuple[dict, str | None]] = []
    answer: list[dict] = []

    async def list_licenses(*, metadata=None, policy=None, limit=100, **_):
        seen.append((dict(metadata or {}), policy))
        return [r for r in answer if policy in (None, r["policy"])][:limit]

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
        (
            {META_EMAIL: "typo+work@example.test", META_TRIAL_KEY: "typo@example.test"},
            None,
        )
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


def both_trials(email: str) -> list[dict]:
    """The earlier trial and the Business one: claimed apart, so one address can hold both."""
    return [
        trial("lic-earlier", email, email),
        trial("lic-business", email, email, policy="policy-business-trial"),
    ]


async def test_an_address_holding_both_trials_asks_which_one(keygen_answers):
    _, answer = keygen_answers
    answer += both_trials("typo@example.test")

    with pytest.raises(LicenseNotFoundError, match="--trial-kind"):
        await find_trial_license_by_email("typo@example.test")


async def test_the_policy_picks_the_business_trial_beside_the_earlier_one(
    keygen_answers,
):
    seen, answer = keygen_answers
    answer += both_trials("typo@example.test")

    record = await find_trial_license_by_email(
        "typo@example.test", policy="policy-business-trial"
    )

    assert record.keygen_license_id == "lic-business"
    assert [policy for _, policy in seen] == ["policy-business-trial"]


async def test_two_trials_of_the_kind_asked_are_a_duplicate(keygen_answers):
    _, answer = keygen_answers
    answer += [
        trial("lic-1", "typo@example.test", "typo@example.test"),
        trial("lic-2", "typo@example.test", "typo@example.test"),
    ]

    with pytest.raises(LicenseNotFoundError, match="resolve the duplicate"):
        await find_trial_license_by_email("typo@example.test", policy="policy-trial")


async def test_an_address_no_trial_was_issued_to_is_not_found(keygen_answers):
    """A lookalike is not a match; support asks again rather than guessing."""
    with pytest.raises(LicenseNotFoundError, match="No trial license"):
        await find_trial_license_by_email("nobody@example.test")


@pytest.fixture
def trial_policies(monkeypatch):
    """Both trial policies set, as with Business trials on."""
    monkeypatch.setattr(config, "KEYGEN_POLICY_TRIAL", "policy-trial")
    monkeypatch.setattr(config, "KEYGEN_POLICY_BUSINESS_TRIAL", "policy-business-trial")


async def support_runs(monkeypatch, command: str) -> int:
    """The script's exit code for the arguments support types."""
    monkeypatch.setattr(sys, "argv", ["correct_license_email", *command.split()])
    return await script.main()


@pytest.mark.parametrize(
    ("kind", "policy", "license_id"),
    [
        ("earlier", "policy-trial", "lic-earlier"),
        ("business", "policy-business-trial", "lic-business"),
    ],
)
async def test_the_script_looks_up_the_trial_kind_support_names(
    keygen_answers, trial_policies, monkeypatch, capsys, kind, policy, license_id
):
    """Each kind reaches the lookup as its own trial's policy."""
    seen, answer = keygen_answers
    answer += both_trials("typo@example.test")
    monkeypatch.setattr("builtins.input", lambda _: "n")

    exit_code = await support_runs(
        monkeypatch,
        f"--trial-email typo@example.test --trial-kind {kind} --email a@b.test",
    )

    assert exit_code == 1  # declined at the confirmation, after the lookup
    assert [asked for _, asked in seen] == [policy]
    assert f"license   {license_id}" in capsys.readouterr().out


async def test_the_script_refuses_a_trial_kind_beside_a_session(
    keygen_answers, trial_policies, monkeypatch, capsys
):
    seen, _ = keygen_answers

    with pytest.raises(SystemExit) as exited:
        await support_runs(
            monkeypatch, "--session cs_x --trial-kind earlier --email a@b.test"
        )

    assert exited.value.code == 2
    assert "--trial-kind goes with --trial-email" in capsys.readouterr().err
    assert seen == []


async def test_the_script_refuses_a_trial_kind_whose_policy_is_unset(
    keygen_answers, trial_policies, monkeypatch, capsys
):
    seen, _ = keygen_answers
    monkeypatch.setattr(config, "KEYGEN_POLICY_BUSINESS_TRIAL", "")

    with pytest.raises(SystemExit) as exited:
        await support_runs(
            monkeypatch,
            "--trial-email typo@example.test --trial-kind business --email a@b.test",
        )

    assert exited.value.code == 2
    assert "needs KEYGEN_POLICY_BUSINESS_TRIAL set" in capsys.readouterr().err
    assert seen == []
