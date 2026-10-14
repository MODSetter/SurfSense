from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def office_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test gets its own Office pack folder."""
    folder = tmp_path / "runtime" / "office"
    monkeypatch.setattr(
        "modules.runtime_packs.office.layout.office_dir", lambda: folder
    )
    return folder
