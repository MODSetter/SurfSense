"""Where each app keeps the models it downloads, on each system.

Each place is the app's documented default, moved where the app itself lets a
person move it: an environment variable, or the small settings file the app
writes. A place that does not exist costs nothing; the readers skip it.
"""

import json
from pathlib import Path

import pytest

from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
    places_to_look,
)

pytestmark = pytest.mark.unit

SYSTEMS = ("win32", "darwin", "linux")


def _roots(places: tuple[Place, ...], app: App) -> list[tuple[Path, Layout]]:
    return [(p.root, p.layout) for p in places if p.app is app]


@pytest.mark.parametrize("system", SYSTEMS)
def test_ollama_keeps_its_models_in_its_home_folder(
    tmp_path: Path, system: str
) -> None:
    """Ollama's default store is `~/.ollama/models` on every system."""
    places = places_to_look(tmp_path, {}, system)

    assert (tmp_path / ".ollama" / "models", Layout.OLLAMA) in _roots(
        places, App.OLLAMA
    )


def test_ollama_models_moved_by_its_variable_are_looked_for_there(
    tmp_path: Path,
) -> None:
    """`OLLAMA_MODELS` moves the store, as Ollama itself reads it."""
    moved = tmp_path / "D" / "ollama"

    places = places_to_look(tmp_path, {"OLLAMA_MODELS": str(moved)}, "win32")

    assert _roots(places, App.OLLAMA)[0] == (moved, Layout.OLLAMA)


def test_linux_ollama_installed_as_a_service_keeps_models_in_its_own_home(
    tmp_path: Path,
) -> None:
    """The Linux install script's service user keeps models under /usr/share/ollama."""
    places = places_to_look(tmp_path, {}, "linux")

    assert (
        Path("/usr/share/ollama/.ollama/models"),
        Layout.OLLAMA,
    ) in _roots(places, App.OLLAMA)


@pytest.mark.parametrize("system", SYSTEMS)
def test_lm_studio_keeps_models_in_its_home_and_its_older_cache(
    tmp_path: Path, system: str
) -> None:
    """LM Studio's `~/.lmstudio/models` and the pre-0.3 cache folder are both read."""
    roots = _roots(places_to_look(tmp_path, {}, system), App.LM_STUDIO)

    assert (tmp_path / ".lmstudio" / "models", Layout.TREE) in roots
    assert (tmp_path / ".cache" / "lm-studio" / "models", Layout.TREE) in roots


def test_lm_studio_moved_by_its_home_pointer_is_looked_for_there(
    tmp_path: Path,
) -> None:
    """The home pointer LM Studio writes moves its models, first in line."""
    moved = tmp_path / "E" / "LM Studio"
    moved.mkdir(parents=True)
    (tmp_path / ".lmstudio-home-pointer").write_text(f"{moved}\n")

    roots = _roots(places_to_look(tmp_path, {}, "darwin"), App.LM_STUDIO)

    assert roots[0] == (moved / "models", Layout.TREE)


@pytest.mark.parametrize("system", SYSTEMS)
def test_the_hugging_face_cache_is_where_every_hub_download_lands(
    tmp_path: Path, system: str
) -> None:
    """With no variable set the hub cache is `~/.cache/huggingface/hub` everywhere."""
    roots = _roots(places_to_look(tmp_path, {}, system), App.HUGGING_FACE)

    assert roots == [(tmp_path / ".cache" / "huggingface" / "hub", Layout.HUB_CACHE)]


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"HF_HUB_CACHE": "/data/hub"}, Path("/data/hub")),
        ({"HUGGINGFACE_HUB_CACHE": "/data/old-hub"}, Path("/data/old-hub")),
        ({"HF_HOME": "/data/hf"}, Path("/data/hf/hub")),
        ({"XDG_CACHE_HOME": "/data/cache"}, Path("/data/cache/huggingface/hub")),
        (
            {"HF_HUB_CACHE": "/data/hub", "HF_HOME": "/data/hf"},
            Path("/data/hub"),
        ),
    ],
)
def test_the_hugging_face_cache_follows_the_variables_the_hub_reads(
    tmp_path: Path, env: dict[str, str], expected: Path
) -> None:
    """HF_HUB_CACHE, then the old name, then HF_HOME, then XDG_CACHE_HOME."""
    roots = _roots(places_to_look(tmp_path, env, "linux"), App.HUGGING_FACE)

    assert roots == [(expected, Layout.HUB_CACHE)]


@pytest.mark.parametrize(
    ("system", "env", "expected"),
    [
        ("linux", {}, Path(".cache/llama.cpp")),
        ("darwin", {}, Path("Library/Caches/llama.cpp")),
        ("win32", {}, Path("AppData/Local/llama.cpp")),
    ],
)
def test_llama_cpp_keeps_its_older_downloads_in_its_own_cache(
    tmp_path: Path, system: str, env: dict[str, str], expected: Path
) -> None:
    """Current builds download into the Hugging Face cache, read above."""
    roots = _roots(places_to_look(tmp_path, env, system), App.LLAMA_CPP)

    assert (tmp_path / expected, Layout.TREE) in roots


def test_llama_cpps_cache_variable_is_read_in_either_layout(tmp_path: Path) -> None:
    """`LLAMA_CACHE` is read as a hub cache and as a flat folder."""
    roots = _roots(
        places_to_look(tmp_path, {"LLAMA_CACHE": "/data/llama"}, "linux"),
        App.LLAMA_CPP,
    )

    assert (Path("/data/llama"), Layout.HUB_CACHE) in roots
    assert (Path("/data/llama"), Layout.TREE) in roots


@pytest.mark.parametrize(
    ("system", "config"),
    [
        ("win32", Path("AppData/Roaming/Jan")),
        ("darwin", Path("Library/Application Support/Jan")),
        ("linux", Path(".config/Jan")),
    ],
)
def test_jan_keeps_models_in_its_data_folder(
    tmp_path: Path, system: str, config: Path
) -> None:
    """Jan's llama.cpp models sit under its data folder in each system's app folder."""
    roots = _roots(places_to_look(tmp_path, {}, system), App.JAN)

    assert (tmp_path / config / "data" / "llamacpp" / "models", Layout.TREE) in roots


def test_jan_moved_by_its_data_folder_setting_is_looked_for_there(
    tmp_path: Path,
) -> None:
    """`data_folder` in Jan's settings moves its models, first in line."""
    moved = tmp_path / "F" / "jan-data"
    settings = tmp_path / "AppData" / "Roaming" / "Jan" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"data_folder": str(moved)}))

    roots = _roots(places_to_look(tmp_path, {}, "win32"), App.JAN)

    assert roots[0] == (moved / "llamacpp" / "models", Layout.TREE)


@pytest.mark.parametrize(
    ("system", "folder"),
    [
        ("win32", Path("AppData/Local/nomic.ai/GPT4All")),
        ("darwin", Path("Library/Application Support/nomic.ai/GPT4All")),
        ("linux", Path(".local/share/nomic.ai/GPT4All")),
    ],
)
def test_gpt4all_keeps_models_in_its_data_folder(
    tmp_path: Path, system: str, folder: Path
) -> None:
    """GPT4All's models folder, per system, as its FAQ lists it."""
    roots = _roots(places_to_look(tmp_path, {}, system), App.GPT4ALL)

    assert (tmp_path / folder, Layout.TREE) in roots


def test_gpt4all_moved_by_its_model_path_setting_is_looked_for_there(
    tmp_path: Path,
) -> None:
    """`modelPath` in GPT4All.ini moves its models, first in line."""
    moved = tmp_path / "G" / "gpt4all-models"
    ini = tmp_path / ".config" / "nomic.ai" / "GPT4All.ini"
    ini.parent.mkdir(parents=True)
    ini.write_text(f"[General]\nmodelPath={moved.as_posix()}\n")

    roots = _roots(places_to_look(tmp_path, {}, "linux"), App.GPT4ALL)

    assert roots[0] == (moved, Layout.TREE)


def test_a_setting_that_will_not_parse_leaves_the_default(tmp_path: Path) -> None:
    """A pointer or settings file that will not parse leaves the app's default."""
    (tmp_path / ".lmstudio-home-pointer").write_bytes(b"\xff\xfe\x00")
    settings = tmp_path / "AppData" / "Roaming" / "Jan" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{not json")

    places = places_to_look(tmp_path, {}, "win32")

    assert (tmp_path / ".lmstudio" / "models", Layout.TREE) in _roots(
        places, App.LM_STUDIO
    )
    assert (
        tmp_path / "AppData" / "Roaming" / "Jan" / "data" / "llamacpp" / "models",
        Layout.TREE,
    ) in _roots(places, App.JAN)


def test_every_place_is_listed_once(tmp_path: Path) -> None:
    """Pointed at the default, a variable must not make a place read twice."""
    env = {"OLLAMA_MODELS": str(tmp_path / ".ollama" / "models")}

    places = places_to_look(tmp_path, env, "darwin")

    keys = [(p.root, p.layout) for p in places]
    assert len(keys) == len(set(keys))
