"""The operations tried on a scratch copy before a version is made of them.

The revise pipeline applies a version's operations all or nothing, and a retried run re-applies
the ones it stored, so one the engine refuses would fail the run every time. A refused operation
changes nothing, so dropping it leaves the others to apply exactly as they did here.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from modules.artifacts.revised_copies.engines import word
from modules.artifacts.revised_copies.engines.report import OpOutcome


class SelfCheckFailedError(Exception):
    """The engine's own check refused the edited copy: an edit it made is not one Word reads."""


def refusals(contract: Path, operations: list[dict]) -> dict[int, OpOutcome]:
    """The operations the engine refuses, by index, each tried on the contract as the ones
    before it left it."""
    with TemporaryDirectory(prefix="surfsense-redline-") as folder:
        report = word.apply(
            contract, operations, Path(folder) / "preflight.docx", partial=True
        )
    if any(n.code == "SELF_CHECK_FAILED" for n in report.must_tell_user):
        raise SelfCheckFailedError(report.must_tell_user[0].message)
    return {o.index: o for o in report.outcomes if o.status != "applied"}
