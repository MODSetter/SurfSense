"""Where other apps keep the GGUF files they download, on each system.

Each place is the app's own default, moved only where the app itself lets a
person move it: an environment variable it reads, or the small settings file it
writes. Nothing else is read here, and a place that does not exist costs the
reader one failed listing.

KoboldCpp is absent on purpose: it saves a model beside its executable, wherever
that was unpacked, so its folder is one a person adds.
"""

import configparser
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class App(StrEnum):
    """Whose folder a model was found in. Keep in sync with `elsewhere-text.ts`."""

    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    HUGGING_FACE = "hugging_face"
    LLAMA_CPP = "llama_cpp"
    JAN = "jan"
    GPT4ALL = "gpt4all"
    # A folder the person added, or a file they picked.
    FOLDER = "folder"


class Layout(StrEnum):
    # Manifests naming content-addressed blobs.
    OLLAMA = "ollama"
    # Hugging Face's `models--<org>--<repo>/snapshots/<commit>/`.
    HUB_CACHE = "hub_cache"
    # GGUF files in folders, named however the app names them.
    TREE = "tree"


@dataclass(frozen=True)
class Place:
    app: App
    root: Path
    layout: Layout
    # How many folders down a TREE is read. LM Studio nests publisher/repo.
    depth: int = 3


def places_to_look(
    home: Path, env: Mapping[str, str], system: str
) -> tuple[Place, ...]:
    """Every place a known app keeps models on `system` ("win32", "darwin" or
    "linux"), whether or not it exists, each once and in this order."""
    dirs = _SystemDirs(home, env, system)
    seen: set[tuple[Path, Layout]] = set()
    places = []
    for place in (
        *_ollama(dirs),
        *_lm_studio(dirs),
        *_hugging_face(dirs),
        *_llama_cpp(dirs),
        *_jan(dirs),
        *_gpt4all(dirs),
    ):
        key = (place.root, place.layout)
        if key not in seen:
            seen.add(key)
            places.append(place)
    return tuple(places)


@dataclass(frozen=True)
class _SystemDirs:
    home: Path
    env: Mapping[str, str]
    system: str

    def var(self, name: str) -> Path | None:
        value = self.env.get(name, "").strip()
        return Path(value) if value else None

    @property
    def config(self) -> Path:
        """Where the app keeps its settings: Roaming, Application Support, XDG."""
        if self.system == "win32":
            return self.var("APPDATA") or self.home / "AppData" / "Roaming"
        if self.system == "darwin":
            return self.home / "Library" / "Application Support"
        return self.var("XDG_CONFIG_HOME") or self.home / ".config"

    @property
    def data(self) -> Path:
        """Where the app keeps its downloads: Local, Application Support, XDG."""
        if self.system == "win32":
            return self.var("LOCALAPPDATA") or self.home / "AppData" / "Local"
        if self.system == "darwin":
            return self.home / "Library" / "Application Support"
        return self.var("XDG_DATA_HOME") or self.home / ".local" / "share"

    @property
    def cache(self) -> Path:
        if self.system == "win32":
            return self.var("LOCALAPPDATA") or self.home / "AppData" / "Local"
        if self.system == "darwin":
            return self.home / "Library" / "Caches"
        return self.var("XDG_CACHE_HOME") or self.home / ".cache"


def _ollama(dirs: _SystemDirs) -> Iterator[Place]:
    yield Place(
        App.OLLAMA,
        dirs.var("OLLAMA_MODELS") or dirs.home / ".ollama" / "models",
        Layout.OLLAMA,
    )
    if dirs.system == "linux":
        # The install script runs Ollama as its own user, with this home.
        yield Place(App.OLLAMA, Path("/usr/share/ollama/.ollama/models"), Layout.OLLAMA)


def _lm_studio(dirs: _SystemDirs) -> Iterator[Place]:
    # LM Studio writes where it moved its home into this file, else uses the default.
    pointed = _read_text(dirs.home / ".lmstudio-home-pointer").strip()
    if pointed and Path(pointed).is_dir():
        yield Place(App.LM_STUDIO, Path(pointed) / "models", Layout.TREE)
    yield Place(App.LM_STUDIO, dirs.home / ".lmstudio" / "models", Layout.TREE)
    # Before 0.3 it kept them in a cache folder, on every system.
    yield Place(
        App.LM_STUDIO, dirs.home / ".cache" / "lm-studio" / "models", Layout.TREE
    )


def _hugging_face(dirs: _SystemDirs) -> Iterator[Place]:
    """The hub's own order: `huggingface-cli`, Unsloth's instructions and current
    llama.cpp's `-hf` all download here."""
    hub = dirs.var("HF_HUB_CACHE") or dirs.var("HUGGINGFACE_HUB_CACHE")
    if hub is None and (hf_home := dirs.var("HF_HOME")):
        hub = hf_home / "hub"
    if hub is None:
        cache = dirs.var("XDG_CACHE_HOME") or dirs.home / ".cache"
        hub = cache / "huggingface" / "hub"
    yield Place(App.HUGGING_FACE, hub, Layout.HUB_CACHE)


def _llama_cpp(dirs: _SystemDirs) -> Iterator[Place]:
    """Older builds saved `-hf` downloads flat in their own cache; a build with
    `LLAMA_CACHE` set keeps the hub's layout there."""
    if moved := dirs.var("LLAMA_CACHE"):
        yield Place(App.LLAMA_CPP, moved, Layout.HUB_CACHE)
        yield Place(App.LLAMA_CPP, moved, Layout.TREE, depth=1)
    yield Place(App.LLAMA_CPP, dirs.cache / "llama.cpp", Layout.TREE, depth=1)


def _jan(dirs: _SystemDirs) -> Iterator[Place]:
    config = dirs.config / "Jan"
    setting = _read_json(config / "settings.json").get("data_folder")
    data = Path(setting) if isinstance(setting, str) and setting else config / "data"
    # Jan's llama.cpp engine: `<model id>/model.gguf`, its projector beside it.
    yield Place(App.JAN, data / "llamacpp" / "models", Layout.TREE, depth=2)
    # Before 0.6: `models/huggingface.co/<org>/<repo>/<file>.gguf`.
    yield Place(App.JAN, data / "models", Layout.TREE, depth=4)


def _gpt4all(dirs: _SystemDirs) -> Iterator[Place]:
    if moved := _gpt4all_model_path(dirs):
        yield Place(App.GPT4ALL, moved, Layout.TREE, depth=1)
    yield Place(App.GPT4ALL, dirs.data / "nomic.ai" / "GPT4All", Layout.TREE, depth=1)


def _gpt4all_model_path(dirs: _SystemDirs) -> Path | None:
    """`modelPath` in the settings GPT4All writes, in its own settings folder."""
    if dirs.system == "darwin":
        ini = dirs.home / ".config" / "gpt4all.io" / "GPT4All.ini"
    else:
        ini = dirs.config / "nomic.ai" / "GPT4All.ini"
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(_read_text(ini))
    except configparser.Error:
        return None
    for section in parser.sections():
        if value := parser.get(section, "modelpath", fallback="").strip():
            return Path(value)
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(_read_text(path) or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
