import os
import sys
from pathlib import Path

# What LibreOffice may see of the caller's environment: enough for the OS to
# start it. Never the rest, which holds SURFSENSE_LOCAL_SECRET, model keys and
# any LIBO_UPDATER_* that would point its updater somewhere.
_FROM_THE_SYSTEM = (
    ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    if sys.platform == "win32"
    else ("PATH", "LANG", "TMPDIR")
)
# Discard: whatever LibreOffice fetches through a proxy goes nowhere.
_NOWHERE = "http://127.0.0.1:9"


def office_environment(home: Path) -> dict[str, str]:
    """LibreOffice's whole environment, built from scratch, with HOME in its profile."""
    allowed = {
        name: os.environ[name] for name in _FROM_THE_SYSTEM if name in os.environ
    }
    proxies = dict.fromkeys(
        ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"), _NOWHERE
    )
    return allowed | proxies | {"HOME": str(home), "no_proxy": "", "NO_PROXY": ""}
