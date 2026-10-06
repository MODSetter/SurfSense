"""Ask an install which LibreOffice it is, under SurfSense's own profile."""

import subprocess
import tempfile
import time

from modules.runtime_packs.office import layout
from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.soffice.convert import (
    LOCK_MARGIN_SECONDS,
    RUN_LIMIT_SECONDS,
)
from modules.runtime_packs.office.soffice.environment import office_environment
from modules.runtime_packs.office.soffice.errors import OfficeFailed, OfficeTimeout
from modules.runtime_packs.office.soffice.profile import profile_url, seed_profile
from modules.runtime_packs.office.soffice.run_lock import run_lock
from worker.document_script.kill_process_tree import process_tree


def report_version(runtime: OfficeRuntime, *, deadline: float) -> str:
    """The version an install reports, such as 26.8.1.1, run under SurfSense's profile."""
    profile = layout.profile_slot()
    with run_lock(layout.run_lock(), wait_until=deadline - LOCK_MARGIN_SECONDS):
        seed_profile(profile)
        command = [
            str(runtime.program),
            f"-env:UserInstallation={profile_url(profile)}",
            "--headless",
            "--version",
        ]
        limit = max(1.0, min(RUN_LIMIT_SECONDS, deadline - time.monotonic()))
        with tempfile.TemporaryFile() as output:
            # Leaving the tree kills soffice.bin too, which a hung run started.
            with process_tree(
                command, office_environment(home=profile), stdout=output
            ) as process:
                try:
                    process.wait(timeout=limit)
                except subprocess.TimeoutExpired as timeout:
                    raise OfficeTimeout(
                        "LibreOffice did not report its version"
                    ) from timeout
            output.seek(0)
            words = output.read().decode(errors="replace").split()
    # "LibreOffice 26.8.1.1 <build id>"
    if len(words) < 2 or not words[1][:1].isdigit():
        raise OfficeFailed("LibreOffice did not report its version")
    return words[1]
