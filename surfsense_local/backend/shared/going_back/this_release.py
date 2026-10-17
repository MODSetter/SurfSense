from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC = Path(__file__).resolve().parents[2] / "alembic"


def this_release_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    return config


def this_release_scripts() -> ScriptDirectory:
    return ScriptDirectory.from_config(this_release_config())


def this_release_head() -> str:
    head = this_release_scripts().get_current_head()
    assert head is not None
    return head
