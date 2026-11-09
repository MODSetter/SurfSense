"""The system's preferred interface languages, most preferred first; empty when unreadable."""

import ctypes
import os
import re
import subprocess
import sys

# GetUserPreferredUILanguages asks for names ("ja-JP") rather than numeric ids.
_MUI_LANGUAGE_NAME = 0x8
_APPLE_TAG = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*")


def system_languages() -> list[str]:
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform == "darwin":
            return _darwin()
        return _posix()
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _windows() -> list[str]:
    count = ctypes.c_ulong()
    size = ctypes.c_ulong()
    get = ctypes.windll.kernel32.GetUserPreferredUILanguages  # type: ignore[attr-defined]
    if not get(_MUI_LANGUAGE_NAME, ctypes.byref(count), None, ctypes.byref(size)):
        return []
    buffer = ctypes.create_unicode_buffer(size.value)
    if not get(_MUI_LANGUAGE_NAME, ctypes.byref(count), buffer, ctypes.byref(size)):
        return []
    # A list of names, each ended by a NUL, the list by a second one.
    return [name for name in buffer[: size.value].split("\0") if name]


def _darwin() -> list[str]:
    output = subprocess.run(
        ["defaults", "read", "-g", "AppleLanguages"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    ).stdout
    return _APPLE_TAG.findall(output)


def _posix() -> list[str]:
    """LANGUAGE lists several; the others name one locale, as `ja_JP.UTF-8`."""
    names = os.environ.get("LANGUAGE", "").split(":")
    names += [os.environ.get(key, "") for key in ("LC_ALL", "LC_MESSAGES", "LANG")]
    tags = [name.split(".")[0].split("@")[0].replace("_", "-") for name in names]
    return [tag for tag in tags if tag and tag not in ("C", "POSIX")]
