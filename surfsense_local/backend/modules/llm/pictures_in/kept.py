"""Whether the chosen image model takes a picture in, kept with the choice.

Read from the connection's model list when the model is chosen, so nothing asks
the network again when a picture is edited or a page needs a reference.
"""

from modules.llm.models import SelectedModel

KEY = "takes_pictures"


def kept_takes_pictures(selected: SelectedModel) -> bool:
    return bool((selected.settings or {}).get(KEY))


def keep_takes_pictures(selected: SelectedModel, takes_pictures: bool) -> None:
    settings = {k: v for k, v in (selected.settings or {}).items() if k != KEY}
    if takes_pictures:
        settings[KEY] = True
    selected.settings = settings or None
