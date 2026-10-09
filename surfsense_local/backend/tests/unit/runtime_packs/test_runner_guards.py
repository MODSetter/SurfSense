"""The runner's guards that need no LibreOffice: the app-wide lock and the profile."""

import sys
import time
import uuid
from pathlib import Path

import psutil
import pytest

from modules.runtime_packs.office import layout
from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.soffice.convert import convert
from modules.runtime_packs.office.soffice.errors import (
    OfficeBusy,
    OfficeMissing,
    OfficeTimeout,
)
from modules.runtime_packs.office.soffice.profile import seed_profile
from modules.runtime_packs.office.soffice.run_lock import run_lock
from modules.runtime_packs.office.soffice.version import report_version

pytestmark = pytest.mark.unit

NO_PROGRAM = OfficeRuntime(Path("no-such-soffice"), "26.8.1.1", "pack")


def test_a_held_lock_ends_the_wait_before_the_deadline(tmp_path: Path) -> None:
    """OfficeBusy comes 20 s before the deadline, and nothing is started."""
    source = tmp_path / "a.docx"
    source.write_bytes(b"PK")
    with run_lock(layout.run_lock(), wait_until=time.monotonic()):
        started = time.monotonic()
        with pytest.raises(OfficeBusy):
            convert(
                source,
                "pdf",
                tmp_path / "out",
                deadline=time.monotonic() + 21,
                runtime=NO_PROGRAM,
            )
    assert time.monotonic() - started < 5
    assert not (tmp_path / "out").exists()


def test_without_office_support_convert_says_why(tmp_path: Path) -> None:
    """No pack and nothing confirmed: the caller reports not_installed."""
    with pytest.raises(OfficeMissing) as missing:
        convert(tmp_path / "a.docx", "pdf", tmp_path, deadline=time.monotonic() + 60)
    assert missing.value.reason == "not_installed"
    assert missing.value.code == "office_missing"


def test_an_unknown_target_format_is_refused(tmp_path: Path) -> None:
    """Only the formats whose output can be checked by its first bytes."""
    with pytest.raises(ValueError):
        convert(tmp_path / "a.docx", "html", tmp_path, deadline=0, runtime=NO_PROGRAM)


def test_the_profile_turns_off_updates_macros_links_and_proxies(tmp_path: Path) -> None:
    """The keys a found install must honour while SurfSense runs it."""
    seed_profile(tmp_path / "slot")
    settings = (tmp_path / "slot" / "user" / "registrymodifications.xcu").read_text()
    for expected in (
        '"OOXMLRecalcMode" oor:op="fuse" oor:type="xs:int"><value>0<',
        '/org.openoffice.Office.Update/Update"><prop oor:name="Enabled" oor:op="fuse" oor:type="xs:boolean"><value>false<',
        '"AutoCheckEnabled" oor:op="fuse" oor:type="xs:boolean"><value>false<',
        '"AutoDownloadEnabled" oor:op="fuse" oor:type="xs:boolean"><value>false<',
        '"DisableMacrosExecution" oor:op="fuse" oor:type="xs:boolean"><value>true<',
        '"ooInetHTTPProxyPort" oor:op="fuse" oor:type="xs:int"><value>9<',
    ):
        assert expected in settings


def test_a_seeded_profile_is_kept_until_a_fresh_one_is_asked_for(
    tmp_path: Path,
) -> None:
    """A warm profile starts faster; a retry starts from a clean one."""
    seed_profile(tmp_path / "slot")
    leftover = tmp_path / "slot" / "user" / "leftover"
    leftover.write_text("from LibreOffice")
    seed_profile(tmp_path / "slot")
    assert leftover.exists()
    seed_profile(tmp_path / "slot", fresh=True)
    assert not leftover.exists()


def _hanging_program(folder: Path, marker: str) -> Path:
    """A stand-in soffice that starts a helper and waits on it, as soffice.com waits on soffice.bin."""
    helper = f'"{sys.executable}" -c "import time; time.sleep(120)" {marker}'
    if sys.platform == "win32":
        program = folder / "soffice.bat"
        program.write_text(f"@{helper}\r\n")
    else:
        program = folder / "soffice"
        program.write_text(f"#!/bin/sh\n{helper}\n")
        program.chmod(0o755)
    return program


def _running(marker: str) -> list[psutil.Process]:
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if marker in (process.info["cmdline"] or ())
    ]


def test_a_version_check_past_its_time_is_killed_with_everything_it_started(
    tmp_path: Path,
) -> None:
    """A hung `--version` leaves no LibreOffice process behind."""
    marker = f"surfsense-hung-{uuid.uuid4().hex}"
    program = _hanging_program(tmp_path, marker)
    try:
        with pytest.raises(OfficeTimeout):
            report_version(
                OfficeRuntime(program, "26.8.1.1", "installed"),
                deadline=time.monotonic() + 3,
            )
        assert _running(marker) == []
    finally:
        for process in _running(marker):
            process.kill()
