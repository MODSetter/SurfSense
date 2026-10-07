"""An installed LibreOffice is offered only on a supported branch with no shared extensions."""

from datetime import date
from pathlib import Path

import pytest

from modules.runtime_packs.office.detect import find_installed
from modules.runtime_packs.office.program import bootstrap_file, program_in, share_dir

pytestmark = pytest.mark.unit

BEFORE_26_8_ENDS = date(2027, 1, 1)


def _install(root: Path, branch: str, extensions: tuple[str, ...] = ()) -> Path:
    program_in(root).parent.mkdir(parents=True, exist_ok=True)
    program_in(root).write_bytes(b"")
    bootstrap_file(root).parent.mkdir(parents=True, exist_ok=True)
    bootstrap_file(root).write_text(
        f"[Bootstrap]\nProductKey=LibreOffice {branch}\n", encoding="utf-8"
    )
    for name in extensions:
        (share_dir(root) / "extensions" / name).mkdir(parents=True)
    return root


def test_a_supported_branch_with_bundled_extensions_is_usable(tmp_path: Path) -> None:
    """Dictionaries and the solver ship with TDF's installer."""
    root = _install(tmp_path / "lo", "26.8", ("dict-en", "nlpsolver", "wiki-publisher"))
    found = find_installed([tmp_path / "missing", root], today=BEFORE_26_8_ENDS)
    assert found is not None
    assert (found.branch, found.refusal) == ("26.8", None)
    assert found.program == program_in(root)


def test_a_branch_past_its_end_is_refused(tmp_path: Path) -> None:
    """26.2 stops getting fixes on 30 Nov 2026."""
    root = _install(tmp_path / "lo", "26.2")
    found = find_installed([root], today=date(2026, 12, 1))
    assert found is not None
    assert found.refusal == "branch_ended"


def test_a_branch_not_listed_is_refused(tmp_path: Path) -> None:
    """25.2, as on the development machine, ended in 2025."""
    root = _install(tmp_path / "lo", "25.2")
    assert (
        find_installed([root], today=BEFORE_26_8_ENDS).refusal == "branch_unsupported"
    )


def test_a_shared_extension_is_refused(tmp_path: Path) -> None:
    """It would load into SurfSense's profile too."""
    root = _install(tmp_path / "lo", "26.8", ("dict-en", "some-macro-pack"))
    assert find_installed([root], today=BEFORE_26_8_ENDS).refusal == "shared_extensions"


def test_an_extension_installed_for_all_users_is_refused(tmp_path: Path) -> None:
    """unopkg --shared puts it in the uno_packages cache."""
    root = _install(tmp_path / "lo", "26.8")
    cache = share_dir(root) / "uno_packages" / "cache" / "uno_packages" / "x.oxt"
    cache.mkdir(parents=True)
    assert find_installed([root], today=BEFORE_26_8_ENDS).refusal == "shared_extensions"


def test_nothing_is_found_where_no_program_is(tmp_path: Path) -> None:
    """An empty folder at a fixed path is not an install."""
    (tmp_path / "lo").mkdir()
    assert find_installed([tmp_path / "lo"]) is None
