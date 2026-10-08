"""SurfSense's own LibreOffice profile, seeded before LibreOffice first opens it.

Key paths are checked against officecfg's schemas on the libreoffice-26-8 branch.
"""

import shutil
from pathlib import Path
from xml.sax.saxutils import escape

_JOBS_UPDATE = (
    "/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['UpdateCheck']"
    "/Arguments"
)
_SCRIPTING = "/org.openoffice.Office.Common/Security/Scripting"
_INET = "/org.openoffice.Inet/Settings"
# Port 9 is discard: a proxy there refuses whatever LibreOffice tries to fetch.
_NOWHERE_HOST, _NOWHERE_PORT = "127.0.0.1", "9"

# (path, name, type, value); a list type's value is its items.
_SETTINGS: tuple[tuple[str, str, str, str | tuple[str, ...]], ...] = (
    # The default is 1, "never": cached zeros would survive the round trip.
    ("/org.openoffice.Office.Calc/Formula/Load", "OOXMLRecalcMode", "xs:int", "0"),
    ("/org.openoffice.Office.Calc/Formula/Load", "ODFRecalcMode", "xs:int", "0"),
    # Updates off three ways: a found install must never update itself through us.
    ("/org.openoffice.Office.Update/Update", "Enabled", "xs:boolean", "false"),
    (_JOBS_UPDATE, "AutoCheckEnabled", "xs:boolean", "false"),
    (_JOBS_UPDATE, "AutoDownloadEnabled", "xs:boolean", "false"),
    # Customer documents are untrusted input.
    (_SCRIPTING, "MacroSecurityLevel", "xs:int", "3"),
    (_SCRIPTING, "DisableMacrosExecution", "xs:boolean", "true"),
    (_SCRIPTING, "BlockUntrustedRefererLinks", "xs:boolean", "true"),
    (_SCRIPTING, "SecureURL", "oor:string-list", ()),
    # Never: Calc's 1, Writer's 2.
    ("/org.openoffice.Office.Calc/Content/Update", "Link", "xs:int", "1"),
    ("/org.openoffice.Office.Writer/Content/Update", "Link", "xs:int", "2"),
    (_INET, "ooInetProxyType", "xs:int", "2"),
    (_INET, "ooInetNoProxy", "xs:string", ""),
    (_INET, "ooInetHTTPProxyName", "xs:string", _NOWHERE_HOST),
    (_INET, "ooInetHTTPProxyPort", "xs:int", _NOWHERE_PORT),
    (_INET, "ooInetHTTPSProxyName", "xs:string", _NOWHERE_HOST),
    (_INET, "ooInetHTTPSProxyPort", "xs:int", _NOWHERE_PORT),
)


def seed_profile(folder: Path, *, fresh: bool = False) -> None:
    """Write the settings into a profile LibreOffice has not opened yet.

    An existing profile is kept unless `fresh`: LibreOffice keeps what it was
    seeded with, and a warm profile starts in a second instead of five.
    """
    settings = folder / "user" / "registrymodifications.xcu"
    if fresh:
        shutil.rmtree(folder, ignore_errors=True)
    elif settings.is_file():
        return
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(_registry(), encoding="utf-8")


def profile_url(folder: Path) -> str:
    """The -env:UserInstallation value LibreOffice expects: a file URL."""
    return folder.resolve().as_uri()


def _registry() -> str:
    items = "\n".join(_item(*setting) for setting in _SETTINGS)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry"'
        ' xmlns:xs="http://www.w3.org/2001/XMLSchema"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        f"{items}\n</oor:items>\n"
    )


def _item(path: str, name: str, kind: str, value: str | tuple[str, ...]) -> str:
    if isinstance(value, tuple):
        body = "".join(f"<it>{escape(v)}</it>" for v in value)
    else:
        body = escape(value)
    return (
        f'<item oor:path="{escape(path, {chr(34): "&quot;"})}">'
        f'<prop oor:name="{name}" oor:op="fuse" oor:type="{kind}">'
        f"<value>{body}</value></prop></item>"
    )
