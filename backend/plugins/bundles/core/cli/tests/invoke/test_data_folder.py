import pytest

pytestmark = pytest.mark.app

COUNTS_ITS_RUNS = """
from surfsense_plugin_sdk import action, data


@action("echo")
def echo(text: str) -> None:
    count = data() / "count.txt"
    runs = int(count.read_text()) + 1 if count.exists() else 1
    count.write_text(str(runs))
    print(runs)
"""


def test_the_plugins_data_is_kept_between_invokes_in_dev_data(
    cli, plugin, real_app
) -> None:
    """The plugin's memory between runs, beside it and never in the app's copy."""
    plugin.write(COUNTS_ITS_RUNS)
    arguments = (
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(real_app.new_workspace()),
    )

    first, second = cli(*arguments), cli(*arguments)

    assert (first.stdout, second.stdout) == ("1\n", "2\n"), second.stderr
    assert (plugin.folder / "dev-data" / "count.txt").read_text() == "2"
