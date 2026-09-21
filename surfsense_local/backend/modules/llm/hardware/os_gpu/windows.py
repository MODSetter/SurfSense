"""Whether Windows itself can see a graphics card.

`Win32_VideoController` through PowerShell, because it needs no dependency and
is present on every supported build. This is the platform where the cross-check
earns its place: a missing backend DLL makes ggml report no devices, silently,
with exit 0, on a machine with a working card.
"""

import subprocess

_COMMAND = [
    "powershell",
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
]
_TIMEOUT_SECONDS = 15.0

# Adapters that are software, not hardware. The measured machine carried a
# Parsec virtual display beside its two real cards, and counting it would report
# a card on a machine that genuinely has none.
_VIRTUAL_MARKERS = (
    "parsec",
    "virtual",
    "remote desktop",
    "basic display",
    "basic render",
    "citrix",
    "vnc",
    "idd",
    "meta driver",
)


def parse_adapters(output: str) -> list[str]:
    """The real adapters in a controller listing, virtual ones dropped."""
    adapters = []
    for line in output.splitlines():
        name = line.strip()
        if not name:
            continue
        if any(marker in name.lower() for marker in _VIRTUAL_MARKERS):
            continue
        adapters.append(name)
    return adapters


def reports_gpu() -> bool | None:
    """True when a real adapter is listed, False when none is, None when unknown."""
    try:
        finished = subprocess.run(
            _COMMAND,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if finished.returncode != 0:
        return None
    return bool(parse_adapters(finished.stdout))
