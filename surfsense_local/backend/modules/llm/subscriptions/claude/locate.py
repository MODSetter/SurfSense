import os
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

# Where Claude Code's installers put it. A GUI app's PATH usually has none of
# these on macOS and Linux, so they are searched after PATH.
_POSIX_UNDER_HOME = (
    ".local/bin/claude",
    ".claude/local/claude",
    ".npm-global/bin/claude",
    ".volta/bin/claude",
)
_POSIX_SYSTEM_WIDE = (
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
    "/home/linuxbrew/.linuxbrew/bin/claude",
    "/usr/bin/claude",
)


# The only Claude Code the Agent SDK runs on Windows: it refuses npm's `claude.cmd`,
# since cmd.exe re-parses its arguments (CVE-2024-27980).
WINDOWS_NAME = "claude.exe"


def _version_key(node_dir: Path) -> tuple[int, ...]:
    """`v22.4.0` as (22, 4, 0); a folder that is not a version ranks below every one."""
    parts = node_dir.name.removeprefix("v").split(".")
    if not all(part.isdecimal() for part in parts):
        return ()
    return tuple(int(part) for part in parts)


def _posix_installed(home: Path) -> Iterator[Path]:
    for relative in _POSIX_UNDER_HOME:
        yield home / relative
    nvm = sorted((home / ".nvm" / "versions" / "node").glob("*"), key=_version_key)
    for node_dir in reversed(nvm):
        yield node_dir / "bin" / "claude"
    for absolute in _POSIX_SYSTEM_WIDE:
        yield Path(absolute)


def _windows_installed(home: Path, env: Mapping[str, str]) -> Iterator[Path]:
    yield home / ".local" / "bin" / "claude.exe"
    if local_app_data := env.get("LOCALAPPDATA"):
        yield Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / "claude.exe"
    if app_data := env.get("APPDATA"):
        # npm's own claude.cmd launcher is skipped: the Agent SDK will not run it.
        yield (
            Path(app_data)
            / "npm"
            / "node_modules"
            / "@anthropic-ai"
            / "claude-code"
            / "bin"
            / "claude.exe"
        )


def _runnable(candidate: Path, windows: bool) -> bool:
    return candidate.is_file() and (windows or os.access(candidate, os.X_OK))


def locate_claude(
    *,
    path_env: str | None,
    home: Path,
    windows: bool = sys.platform == "win32",
    env: Mapping[str, str] = os.environ,
) -> Path | None:
    """The user's own Claude Code; SurfSense ships none."""
    name = WINDOWS_NAME if windows else "claude"
    on_path = (Path(d) / name for d in (path_env or "").split(os.pathsep) if d)
    installed = _windows_installed(home, env) if windows else _posix_installed(home)
    for candidate in (*on_path, *installed):
        if _runnable(candidate, windows):
            return candidate
    return None


def this_machines_claude() -> Path | None:
    """The Claude Code this process can run, found on its own PATH and home."""
    return locate_claude(path_env=os.environ.get("PATH"), home=Path.home())
