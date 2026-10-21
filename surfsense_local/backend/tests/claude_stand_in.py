"""A `claude` that answers `--version` and `auth status` as Claude Code 2.1.301 did.

The answers come from a Python script, launched through `claude.cmd` on Windows
and a shell launcher elsewhere, so the same tests run on all three systems.
"""

import json
import os
import shlex
import sys
from pathlib import Path

SIGNED_IN = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "email": "ada@example.com",
    "orgId": "org-ada",
    "orgName": "Ada's Org",
    "subscriptionType": "max",
}
SIGNED_OUT = {"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty"}

_PROGRAM = """\
import json, os, sys, time
if {env_log!r}:
    with open({env_log!r}, "w") as log:
        json.dump(dict(os.environ), log)
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
    env_log: Path | None = None,
) -> Path:
    """Write the stand-in into `directory`; a string `auth` is printed as is.

    With `env_log`, each run writes the environment it was started with there.
    """
    program = directory / "claude_stand_in_program.py"
    program.write_text(
        _PROGRAM.format(
            hang_seconds=hang_seconds,
            env_log=str(env_log) if env_log else "",
            version=version,
            auth=auth if isinstance(auth, str) else json.dumps(auth),
        )
    )
    launcher = directory / ("claude.cmd" if sys.platform == "win32" else "claude")
    replaced = launcher.stat().st_mtime_ns if launcher.exists() else None
    if sys.platform == "win32":
        launcher.write_text(f'@"{sys.executable}" "{program}" %*\r\n')
    else:
        python, script = shlex.quote(sys.executable), shlex.quote(str(program))
        launcher.write_text(f'#!/bin/sh\nexec {python} {script} "$@"\n')
        launcher.chmod(0o755)
    if replaced is not None:
        # Rewritten within milliseconds, and NTFS may keep the old time: a second
        # on, so the version read per binary as installed sees another install.
        later = max(launcher.stat().st_mtime_ns, replaced + 1_000_000_000)
        os.utime(launcher, ns=(later, later))
    return launcher
