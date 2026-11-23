"""Looking for models elsewhere on this computer: where, whether, and the file
or folder a person picks when what they want is somewhere else.

Each look reads the record, then every place it allows: the known apps' folders
while looking is on, and the folders a person added, which are their own act and
read either way. The Docker image has neither: its browser cannot name a path
on the server, and the container holds no other app's folder.
"""

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import (
    Finding,
    FoundModel,
    find_file,
    find_models,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
    places_to_look,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.record import (
    ElsewhereRecord,
    add_folder,
    read_record,
    remove_folder,
    set_look,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.runs_here import (
    IN_MODELS_FOLDER,
    NOT_FOUND,
    Unusable,
)

# How many folders down a folder a person added is read.
FOLDER_DEPTH = 4


@dataclass(frozen=True)
class Surroundings:
    """Where this computer's other apps keep their models: the home folder, the
    environment those apps read, and the system."""

    home: Path
    env: Mapping[str, str]
    system: str

    @classmethod
    def of_this_process(cls) -> "Surroundings":
        return cls(Path.home(), dict(os.environ), sys.platform)


class PickRefusedError(Exception):
    def __init__(self, unusable: Unusable) -> None:
        super().__init__(unusable.reason)
        self.unusable = unusable


@dataclass(frozen=True)
class Look:
    record: ElsewhereRecord
    # The known apps whose folder exists here: what the screen says it read.
    looked_in: tuple[App, ...]
    finding: Finding


class Elsewhere:
    def __init__(self, models_dir: Path, surroundings: Surroundings | None) -> None:
        self._models_dir = models_dir
        self._surroundings = surroundings

    @property
    def available(self) -> bool:
        return self._surroundings is not None

    def look(self) -> Look:
        record = read_record(self._models_dir)
        if self._surroundings is None:
            return Look(record, (), Finding())
        known = (
            places_to_look(
                self._surroundings.home,
                self._surroundings.env,
                self._surroundings.system,
            )
            if record.look
            else ()
        )
        added = tuple(
            Place(App.FOLDER, Path(folder), Layout.TREE, depth=FOLDER_DEPTH)
            for folder in record.folders
        )
        finding = find_models((*known, *added), exclude=[self._models_dir])
        return Look(record, _existing_apps(known), finding)

    def pick_file(self, path: Path) -> FoundModel:
        """A file a person picked, as the scan would offer it, or why not."""
        self._refuse_where_unavailable()
        if not path.is_absolute() or not path.is_file():
            raise PickRefusedError(NOT_FOUND)
        if self._inside_models_folder(path):
            raise PickRefusedError(IN_MODELS_FOLDER)
        outcome = find_file(path)
        if not isinstance(outcome, FoundModel):
            raise PickRefusedError(outcome.unusable)
        return outcome

    def add_folder(self, folder: Path) -> None:
        self._refuse_where_unavailable()
        if not folder.is_absolute() or not folder.is_dir():
            raise PickRefusedError(NOT_FOUND)
        if self._inside_models_folder(folder):
            raise PickRefusedError(IN_MODELS_FOLDER)
        add_folder(self._models_dir, folder)

    def remove_folder(self, folder: Path) -> None:
        remove_folder(self._models_dir, folder)

    def set_look(self, look: bool) -> None:
        set_look(self._models_dir, look)

    def _refuse_where_unavailable(self) -> None:
        if self._surroundings is None:
            raise PickRefusedError(NOT_FOUND)

    def _inside_models_folder(self, path: Path) -> bool:
        try:
            return path.resolve().is_relative_to(self._models_dir.resolve())
        except OSError:
            return False


def _existing_apps(places: tuple[Place, ...]) -> tuple[App, ...]:
    apps: list[App] = []
    for place in places:
        try:
            exists = place.root.is_dir()
        except OSError:
            exists = False
        if exists and place.app not in apps:
            apps.append(place.app)
    return tuple(apps)
