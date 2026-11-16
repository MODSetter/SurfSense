import sys

import pytest

from modules.plugins.lists.registry import registry_origin

pytestmark = pytest.mark.unit


def test_a_checkout_trusts_its_own_unsigned_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What a plugin author edits shows up without signing it."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("SURFSENSE_LOCAL_SIGNED_REGISTRY", raising=False)

    assert registry_origin.reads_repository()


def test_the_container_reads_the_signed_registry_though_it_runs_from_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Docker image runs a venv backend, which `sys.frozen` would call a checkout."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("SURFSENSE_LOCAL_SIGNED_REGISTRY", "1")

    assert not registry_origin.reads_repository()


def test_a_packaged_app_reads_the_signed_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the list the plugin host signed reaches a release."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SURFSENSE_LOCAL_SIGNED_REGISTRY", raising=False)

    assert not registry_origin.reads_repository()
