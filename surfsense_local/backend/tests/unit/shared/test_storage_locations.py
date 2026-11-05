"""Where the desktop's movable and fixed folders are, as the environment names them."""

from pathlib import Path

import pytest

from shared.config import StorageSettings


def test_embedders_stay_in_the_data_folder_unless_the_models_folder_moved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Downloaded embedders are heavy, so they go where the models folder went."""
    monkeypatch.delenv("SURFSENSE_LOCAL_EMBEDDING_MODELS_DIR", raising=False)
    assert StorageSettings(data_dir=tmp_path).embedding_models_dir == (
        tmp_path / "embeddings"
    )

    moved = tmp_path / "other-drive" / "embeddings"
    monkeypatch.setenv("SURFSENSE_LOCAL_EMBEDDING_MODELS_DIR", str(moved))
    assert StorageSettings(data_dir=tmp_path).embedding_models_dir == moved


def test_the_shells_settings_can_stay_behind_when_the_data_moves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The usage summary reads the language from Electron's folder, which never moves."""
    monkeypatch.delenv("SURFSENSE_LOCAL_SHELL_SETTINGS_DIR", raising=False)
    assert StorageSettings(data_dir=tmp_path).shell_settings_dir == (
        tmp_path / "electron"
    )

    fixed = tmp_path / "home" / ".surfsense" / "electron"
    monkeypatch.setenv("SURFSENSE_LOCAL_SHELL_SETTINGS_DIR", str(fixed))
    assert StorageSettings(data_dir=tmp_path).shell_settings_dir == fixed
