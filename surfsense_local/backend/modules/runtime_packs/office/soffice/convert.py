"""Convert a copy of one file with LibreOffice, one run at a time, app-wide.

Only outside a database transaction and outside the engine child: a slow run
must not hold either. The customer's file is only ever copied.
"""

import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import IO

from modules.runtime_packs.office import layout
from modules.runtime_packs.office.runtime import OfficeRuntime, require_runtime
from modules.runtime_packs.office.soffice.environment import office_environment
from modules.runtime_packs.office.soffice.errors import OfficeFailed, OfficeTimeout
from modules.runtime_packs.office.soffice.profile import profile_url, seed_profile
from modules.runtime_packs.office.soffice.render_copy import neutralize_external
from modules.runtime_packs.office.soffice.run_lock import run_lock
from shared import cancellation
from worker.document_script.kill_process_tree import process_tree

# The lock wait ends this long before the deadline, so a run that starts has time.
LOCK_MARGIN_SECONDS = 20
# No conversion gets longer: three small files peaked at 400 MB (measured).
RUN_LIMIT_SECONDS = 90
# A retry with a fresh profile only when this much is left.
RETRY_FLOOR_SECONDS = 30
STDERR_TAIL_BYTES = 16 * 1024
_POLL_SECONDS = 0.5

FILTERS = {
    "pdf": "pdf",
    "docx": "docx:MS Word 2007 XML",
    "xlsx": "xlsx:Calc MS Excel 2007 XML",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
}
_MAGIC = {"pdf": b"%PDF-"}
_ZIP = b"PK"
_PROFILE_TROUBLE = ("user installation", "profile")


def convert(
    source: Path,
    target_format: str,
    out_dir: Path,
    *,
    deadline: float,
    runtime: OfficeRuntime | None = None,
) -> Path:
    """Write `<out_dir>/<source stem>.<target_format>` from a copy of `source`.

    `deadline` is a time.monotonic() value. `runtime` defaults to office_runtime();
    tests name one. Raises OfficeMissing, OfficeBusy, OfficeTimeout or OfficeFailed.
    """
    if target_format not in FILTERS:
        raise ValueError(f"cannot convert to {target_format!r}")
    office = runtime or require_runtime()
    with run_lock(layout.run_lock(), wait_until=deadline - LOCK_MARGIN_SECONDS):
        work_root = layout.office_dir() / "tmp"
        work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work_root) as work:
            produced = _convert_copy(
                office, source, target_format, Path(work), deadline
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / f"{source.stem}.{target_format}"
            shutil.move(produced, target)
            return target


def _convert_copy(
    office: OfficeRuntime, source: Path, target_format: str, work: Path, deadline: float
) -> Path:
    """Convert a neutralized copy, retrying once on a fresh profile when time allows."""
    copy = work / "in" / f"document{source.suffix.lower()}"
    copy.parent.mkdir()
    shutil.copyfile(source, copy)
    neutralize_external(copy)
    profile = layout.profile_slot()
    seed_profile(profile)
    try:
        return _run(office, copy, target_format, work / "out", profile, deadline)
    except (OfficeTimeout, OfficeFailed) as error:
        retry = isinstance(error, OfficeTimeout) or _profile_trouble(str(error))
        if not retry or deadline - time.monotonic() < RETRY_FLOOR_SECONDS:
            raise
    seed_profile(profile, fresh=True)
    return _run(office, copy, target_format, work / "out-retry", profile, deadline)


def _run(
    office: OfficeRuntime,
    copy: Path,
    target_format: str,
    out: Path,
    profile: Path,
    deadline: float,
) -> Path:
    limit = min(RUN_LIMIT_SECONDS, deadline - time.monotonic())
    if limit <= 0:
        raise OfficeTimeout("no time was left to run LibreOffice")
    out.mkdir()
    command = [
        str(office.program),
        f"-env:UserInstallation={profile_url(profile)}",
        "--headless",
        "--invisible",
        "--nodefault",
        "--nolockcheck",
        "--nologo",
        "--norestore",
        "--convert-to",
        FILTERS[target_format],
        "--outdir",
        str(out),
        str(copy),
    ]
    with process_tree(command, office_environment(home=profile)) as process:
        stderr = _Tail(process.stderr)
        exit_code = _wait(process, limit)
    if exit_code is None:
        raise OfficeTimeout(f"LibreOffice took longer than {limit:.0f} s")
    produced = out / f"{copy.stem}.{target_format}"
    if not _looks_whole(produced, target_format):
        last_words = stderr.text().strip().splitlines()[-1:] or [f"exit {exit_code}"]
        raise OfficeFailed(f"LibreOffice wrote no {target_format}: {last_words[0]}")
    return produced


def _wait(process: subprocess.Popen, limit: float) -> int | None:
    """The exit code, or None at the limit; the caller's exit kills the tree."""
    ends = time.monotonic() + limit
    while (left := ends - time.monotonic()) > 0:
        try:
            return process.wait(timeout=min(_POLL_SECONDS, left))
        except subprocess.TimeoutExpired:
            cancellation.raise_if_cancelled()
    return None


def _looks_whole(path: Path, target_format: str) -> bool:
    """Success is a file that starts like its format; the exit code is not trusted."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        return handle.read(5).startswith(_MAGIC.get(target_format, _ZIP))


def _profile_trouble(message: str) -> bool:
    lowered = message.lower()
    return any(sign in lowered for sign in _PROFILE_TROUBLE)


class _Tail:
    """Drains stderr on a thread, keeping the end, so a chatty run never blocks."""

    def __init__(self, pipe: IO[bytes]) -> None:
        self._tail = bytearray()
        self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with pipe:
            while chunk := pipe.read1(65536):
                self._tail += chunk
                del self._tail[:-STDERR_TAIL_BYTES]

    def text(self) -> str:
        self._thread.join(1)
        return bytes(self._tail).decode(errors="replace")
