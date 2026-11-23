"""What SurfSense remembers about models it uses where other apps keep them.

The record lives beside the preset in the models folder, so it moves with the
folder, and it holds paths and names only: the files stay the other app's.
"""

import threading
import time
from pathlib import Path

import pytest

from modules.llm.catalog.local.engines.llamacpp.elsewhere import (
    record as record_module,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import (
    FoundModel,
    find_models,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.record import (
    RECORD_FILE,
    add_folder,
    forget,
    in_place_path,
    read_record,
    remove_folder,
    set_look,
    use_in_place,
)
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    chat_model_bytes,
    ollama_store,
    write_chat_model,
)

pytestmark = pytest.mark.unit


def _found(place: Place) -> list[FoundModel]:
    return list(find_models([place]).models)


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    """SurfSense's own models folder, empty."""
    folder = tmp_path / "surfsense-models"
    folder.mkdir()
    return folder


def test_a_model_used_in_place_is_named_for_its_app_and_model(
    tmp_path: Path, models_dir: Path
) -> None:
    """The runtime's name for it starts with whose file it is, and leads back to it."""
    blob, _ = ollama_store(tmp_path / "ollama", "qwen3", "8b", chat_model_bytes())
    (found,) = _found(Place(App.OLLAMA, tmp_path / "ollama", Layout.OLLAMA))

    used = use_in_place(models_dir, found)

    assert used.model_id == "ollama-qwen3-8b"
    assert in_place_path(models_dir, used.model_id) == blob
    assert read_record(models_dir).models == (used,)


def test_using_the_same_file_again_keeps_its_name(
    tmp_path: Path, models_dir: Path
) -> None:
    """Using a file twice records it once, under the first name."""
    write_chat_model(tmp_path / "pub" / "repo" / "Qwen3-8B-Q4_K_M.gguf")
    (found,) = _found(Place(App.LM_STUDIO, tmp_path, Layout.TREE))

    first = use_in_place(models_dir, found)
    second = use_in_place(models_dir, found)

    assert first == second
    assert len(read_record(models_dir).models) == 1


def test_two_builds_of_one_model_get_names_of_their_own(
    tmp_path: Path, models_dir: Path
) -> None:
    """Two quantizations of one model never share a runtime name."""
    repo = tmp_path / "pub" / "repo"
    write_chat_model(repo / "Qwen3-8B-Q4_K_M.gguf", name="Qwen3 8B")
    write_chat_model(repo / "Qwen3-8B-Q8_0.gguf", name="Qwen3 8B", file_type=7)
    found = _found(Place(App.LM_STUDIO, tmp_path, Layout.TREE))

    ids = sorted(use_in_place(models_dir, model).model_id for model in found)

    assert ids == ["lmstudio-Qwen3-8B-Q4_K_M", "lmstudio-Qwen3-8B-Q8_0"]


def test_a_name_never_shadows_a_file_in_the_models_folder(
    tmp_path: Path, models_dir: Path
) -> None:
    """The router lists the folder's files by name; a preset section of the same
    name would replace one of them."""
    (models_dir / "ollama-qwen3-8b.gguf").write_bytes(b"GGUF")
    ollama_store(tmp_path / "ollama", "qwen3", "8b", chat_model_bytes())
    (found,) = _found(Place(App.OLLAMA, tmp_path / "ollama", Layout.OLLAMA))

    assert use_in_place(models_dir, found).model_id == "ollama-qwen3-8b-2"


def test_forgetting_a_model_leaves_its_file_and_the_others(
    tmp_path: Path, models_dir: Path
) -> None:
    """Forgetting drops one record, touches no file, and says when it had none."""
    ollama_store(tmp_path / "ollama", "qwen3", "8b", chat_model_bytes(name="A"))
    ollama_store(tmp_path / "ollama", "llama3.2", "3b", chat_model_bytes(name="B"))
    one, two = _found(Place(App.OLLAMA, tmp_path / "ollama", Layout.OLLAMA))
    kept = use_in_place(models_dir, one)
    gone = use_in_place(models_dir, two)

    assert forget(models_dir, gone.model_id) is True

    assert read_record(models_dir).models == (kept,)
    assert two.path.exists()
    assert forget(models_dir, gone.model_id) is False


def test_looking_and_added_folders_are_remembered(
    tmp_path: Path, models_dir: Path
) -> None:
    """The switch and the added folders persist, each folder once."""
    assert read_record(models_dir).look is True

    set_look(models_dir, False)
    add_folder(models_dir, tmp_path / "D" / "models")
    add_folder(models_dir, tmp_path / "D" / "models")

    record = read_record(models_dir)
    assert record.look is False
    assert record.folders == (str(tmp_path / "D" / "models"),)

    remove_folder(models_dir, tmp_path / "D" / "models")

    assert read_record(models_dir).folders == ()


def test_a_record_that_will_not_parse_reads_as_a_fresh_one(models_dir: Path) -> None:
    """A damaged record reads as looking on, no folders and no models."""
    (models_dir / RECORD_FILE).write_text("{oops")

    record = read_record(models_dir)

    assert (record.look, record.folders, record.models) == (True, (), ())


def test_changes_made_at_once_all_land(
    tmp_path: Path, models_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The routes run in threads: the switch, a folder and a model recorded at
    the same moment each keep their change, and each write is whole."""
    real_write = record_module.write_record

    def slow_write(folder: Path, record) -> None:
        time.sleep(0.05)  # widen the window two unserialised writers race in
        real_write(folder, record)

    monkeypatch.setattr(record_module, "write_record", slow_write)
    ollama_store(tmp_path / "ollama", "qwen3", "8b", chat_model_bytes())
    (found,) = _found(Place(App.OLLAMA, tmp_path / "ollama", Layout.OLLAMA))
    work = [
        lambda: set_look(models_dir, False),
        lambda: add_folder(models_dir, tmp_path / "D" / "models"),
        lambda: use_in_place(models_dir, found),
    ]
    threads = [threading.Thread(target=step) for step in work]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    record = read_record(models_dir)
    assert record.look is False
    assert record.folders == (str(tmp_path / "D" / "models"),)
    assert [m.model_id for m in record.models] == ["ollama-qwen3-8b"]
    assert sorted(p.name for p in models_dir.iterdir()) == [RECORD_FILE]
