from __future__ import annotations

import sys
from uuid import UUID

import pytest

from scripts import purge_hosted_accounts as purge

pytestmark = pytest.mark.unit

_ACCOUNTS = [
    (UUID("00000000-0000-0000-0000-000000000001"), "ada@example.com"),
    (UUID("00000000-0000-0000-0000-000000000002"), "bob@example.com"),
    (UUID("00000000-0000-0000-0000-000000000003"), "cy@example.com"),
]


def _argv(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["purge_hosted_accounts", *args])


async def test_refuses_outside_sunset_mode(monkeypatch, capsys):
    _argv(monkeypatch, "--execute", "--yes")
    monkeypatch.setattr(purge, "is_sunset_mode", lambda: False)

    async def accounts():
        pytest.fail("accounts must not be read before the sunset guard")

    monkeypatch.setattr(purge, "_accounts", accounts)

    assert await purge.main() == 2
    assert "SUNSET_MODE is not set" in capsys.readouterr().err


async def test_defaults_to_a_dry_run(monkeypatch, capsys):
    _argv(monkeypatch)
    monkeypatch.setattr(purge, "is_sunset_mode", lambda: True)

    async def accounts():
        return _ACCOUNTS

    erased = []

    async def erase(user_id):
        erased.append(user_id)

    monkeypatch.setattr(purge, "_accounts", accounts)
    monkeypatch.setattr(purge, "erase_account", erase)

    assert await purge.main() == 0
    assert erased == []
    assert "Dry run. Nothing was changed." in capsys.readouterr().out


async def test_wrong_confirmation_aborts_without_erasing(monkeypatch, capsys):
    _argv(monkeypatch, "--execute")
    monkeypatch.setattr(purge, "is_sunset_mode", lambda: True)

    async def accounts():
        return _ACCOUNTS

    erased = []

    async def erase(user_id):
        erased.append(user_id)

    monkeypatch.setattr(purge, "_accounts", accounts)
    monkeypatch.setattr(purge, "erase_account", erase)
    monkeypatch.setattr("builtins.input", lambda _prompt: "not the confirmation")

    assert await purge.main() == 1
    assert erased == []
    assert "Aborted." in capsys.readouterr().err


async def test_failure_is_recorded_and_the_purge_continues(monkeypatch, capsys):
    _argv(monkeypatch, "--execute", "--yes")
    monkeypatch.setattr(purge, "is_sunset_mode", lambda: True)

    async def accounts():
        return _ACCOUNTS

    erased = []

    async def erase(user_id):
        erased.append(user_id)
        if user_id == _ACCOUNTS[0][0]:
            raise RuntimeError("blob cleanup failed")

    async def remaining():
        return 1

    monkeypatch.setattr(purge, "_accounts", accounts)
    monkeypatch.setattr(purge, "erase_account", erase)
    monkeypatch.setattr(purge, "_remaining", remaining)

    assert await purge.main() == 1
    assert erased == [account[0] for account in _ACCOUNTS]
    captured = capsys.readouterr()
    assert "Erased 2 account(s)." in captured.out
    assert "blob cleanup failed" in captured.err
    assert "re-run to retry the failures" in captured.err


async def test_limit_bounds_the_accounts_erased(monkeypatch):
    _argv(monkeypatch, "--execute", "--yes", "--limit", "2")
    monkeypatch.setattr(purge, "is_sunset_mode", lambda: True)

    async def accounts():
        return _ACCOUNTS

    erased = []

    async def erase(user_id):
        erased.append(user_id)

    async def remaining():
        return 1

    monkeypatch.setattr(purge, "_accounts", accounts)
    monkeypatch.setattr(purge, "erase_account", erase)
    monkeypatch.setattr(purge, "_remaining", remaining)

    assert await purge.main() == 0
    assert erased == [account[0] for account in _ACCOUNTS[:2]]
