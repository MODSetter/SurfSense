import pytest

pytestmark = pytest.mark.unit


def test_data_is_the_folder_the_app_keeps_for_the_plugin(plugin) -> None:
    """What a plugin writes there is still there on its next run."""
    plugin.write(
        """
from surfsense_plugin_sdk import action, data


@action("echo")
def echo(text: str) -> None:
    (data() / "last.txt").write_text(text)
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert (plugin.data / "last.txt").read_text() == "hi"
