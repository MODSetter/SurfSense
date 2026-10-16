import sys
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude.locate import locate_claude

pytestmark = pytest.mark.unit
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows has no executable bit"
)


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_claude_on_path_is_found(tmp_path: Path) -> None:
    """A Claude Code the PATH names is the one used."""
    on_path = _executable(tmp_path / "bin" / "claude")

    found = locate_claude(
        path_env=str(on_path.parent), home=tmp_path / "home", windows=False
    )

    assert found == on_path


def test_native_install_is_found_when_path_lacks_it(tmp_path: Path) -> None:
    """A GUI app's PATH misses ~/.local/bin, where Claude Code's installer links it."""
    home = tmp_path / "home"
    installed = _executable(home / ".local" / "bin" / "claude")

    found = locate_claude(path_env="/usr/bin:/bin", home=home, windows=False)

    assert found == installed


@posix_only
def test_a_file_that_cannot_run_is_skipped(tmp_path: Path) -> None:
    """A non-executable file at an install location is passed over for the next."""
    home = tmp_path / "home"
    broken = home / ".local" / "bin" / "claude"
    broken.parent.mkdir(parents=True)
    broken.write_text("not a program")
    older = _executable(home / ".claude" / "local" / "claude")

    found = locate_claude(path_env="/usr/bin:/bin", home=home, windows=False)

    assert found == older


@pytest.mark.skipif(
    any(
        Path(p).exists() for p in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude")
    ),
    reason="this machine has a system-wide Claude Code",
)
def test_nothing_found_is_none(tmp_path: Path) -> None:
    """No Claude Code anywhere is no binary, not an error."""
    assert (
        locate_claude(path_env="/usr/bin:/bin", home=tmp_path / "home", windows=False)
        is None
    )


def test_windows_native_install_is_found_when_path_lacks_it(tmp_path: Path) -> None:
    """The Windows installer puts claude.exe under %USERPROFILE%\\.local\\bin."""
    home = tmp_path / "home"
    installed = _executable(home / ".local" / "bin" / "claude.exe")

    found = locate_claude(path_env="", home=home, windows=True, env={})

    assert found == installed


def test_newest_nvm_node_is_preferred(tmp_path: Path) -> None:
    """With several nvm Node versions, the newest one's global claude is used."""
    home = tmp_path / "home"
    node = home / ".nvm" / "versions" / "node"
    _executable(node / "v9.11.2" / "bin" / "claude")
    newest = _executable(node / "v22.4.0" / "bin" / "claude")

    found = locate_claude(path_env="/usr/bin:/bin", home=home, windows=False)

    assert found == newest


def test_windows_npm_launcher_is_passed_over_for_its_executable(
    tmp_path: Path,
) -> None:
    """npm puts claude.cmd on PATH; the Agent SDK refuses it, so its claude.exe is used."""
    app_data = tmp_path / "Roaming"
    launcher = _executable(app_data / "npm" / "claude.cmd")
    real = _executable(
        app_data
        / "npm"
        / "node_modules"
        / "@anthropic-ai"
        / "claude-code"
        / "bin"
        / "claude.exe"
    )

    found = locate_claude(
        path_env=str(launcher.parent),
        home=tmp_path / "home",
        windows=True,
        env={"APPDATA": str(app_data)},
    )

    assert found == real


def test_windows_winget_link_is_found(tmp_path: Path) -> None:
    """WinGet links the executable into its Links folder under %LOCALAPPDATA%."""
    local = tmp_path / "Local"
    link = _executable(local / "Microsoft" / "WinGet" / "Links" / "claude.exe")

    found = locate_claude(
        path_env="",
        home=tmp_path / "home",
        windows=True,
        env={"LOCALAPPDATA": str(local)},
    )

    assert found == link


def test_windows_nothing_found_is_none(tmp_path: Path) -> None:
    """Windows has no system-wide location to search, so an empty home finds nothing."""
    assert (
        locate_claude(path_env="", home=tmp_path / "home", windows=True, env={}) is None
    )


def test_a_folder_that_is_not_a_node_version_is_tried_last(tmp_path: Path) -> None:
    """nvm names each Node folder vX.Y.Z; anything else there ranks below them."""
    home = tmp_path / "home"
    node = home / ".nvm" / "versions" / "node"
    _executable(node / "system" / "bin" / "claude")
    versioned = _executable(node / "v18.20.1" / "bin" / "claude")

    found = locate_claude(path_env="/usr/bin:/bin", home=home, windows=False)

    assert found == versioned
