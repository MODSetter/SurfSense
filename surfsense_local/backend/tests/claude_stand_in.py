"""A `claude` that answers `--version` and `auth status` as Claude Code 2.1.301 did.

The answers come from a Python script, launched through `claude.cmd` on Windows
and a shell launcher elsewhere, so the same tests run on all three systems.
"""

import json
import shlex
import sys
from pathlib import Path

SIGNED_IN = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "email": "ada@example.com",
    "orgName": "Ada's Org",
    "subscriptionType": "max",
}
SIGNED_OUT = {"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty"}

_PROGRAM = """\
import sys, time
time.sleep({hang_seconds!r})
if sys.argv[1:] == ["--version"]:
    print({version!r})
elif sys.argv[1:] == ["auth", "status"]:
    print({auth!r})
else:
    sys.exit(2)
"""


def claude_stand_in(
    directory: Path,
    *,
    version: str = "2.1.301 (Claude Code)",
    auth: dict | str = SIGNED_IN,
    hang_seconds: float = 0,
) -> Path:
    """Write the stand-in into `directory`; a string `auth` is printed as is."""
    program = directory / "claude_stand_in_program.py"
    program.write_text(
        _PROGRAM.format(
            hang_seconds=hang_seconds,
            version=version,
            auth=auth if isinstance(auth, str) else json.dumps(auth),
        )
    )
    if sys.platform == "win32":
        launcher = directory / "claude.cmd"
        launcher.write_text(f'@"{sys.executable}" "{program}" %*\r\n')
    else:
        launcher = directory / "claude"
        python, script = shlex.quote(sys.executable), shlex.quote(str(program))
        launcher.write_text(f'#!/bin/sh\nexec {python} {script} "$@"\n')
        launcher.chmod(0o755)
    return launcher
