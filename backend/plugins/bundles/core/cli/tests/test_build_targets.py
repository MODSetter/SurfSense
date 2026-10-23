import platform
import sys

import pytest
import typer

from surfsense_plugin_cli.build_targets import this_platform

pytestmark = pytest.mark.unit


def test_a_machine_plugins_are_not_built_for_is_told_which_are(
    monkeypatch, capsys
) -> None:
    """Named with the platforms that are supported, not failing later inside uv.

    Called directly: the command cannot be started on a system it does not run on.
    """
    monkeypatch.setattr(sys, "platform", "freebsd14")
    monkeypatch.setattr(platform, "machine", lambda: "riscv64")

    with pytest.raises(typer.Exit):
        this_platform()

    message = capsys.readouterr().err
    assert "this machine is freebsd14-x64" in message
    assert "linux-x64" in message
