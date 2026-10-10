import pytest

pytestmark = pytest.mark.app

PRINTS_ITS_TOKEN = """
from surfsense_plugin_sdk import action, secret


@action("echo")
def echo(text: str) -> None:
    print(secret("token"))
"""


def _declaring_a_token(plugin) -> None:
    """The secret the plugin reads, as its manifest declares it."""
    plugin.manifest["secrets"] = [{"name": "token", "title": "API token"}]
    plugin.write(PRINTS_ITS_TOKEN)


def _invoke(cli, plugin, real_app, environment=None, typed=None):
    """Invoke the token plugin, giving the secret whichever way the test says."""
    return cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(real_app.new_workspace()),
        environment=environment,
        typed=typed,
    )


def test_a_secret_comes_from_the_authors_own_environment(cli, plugin, real_app) -> None:
    """The same variable the app hands the plugin, set in the author's shell."""
    _declaring_a_token(plugin)

    finished = _invoke(
        cli, plugin, real_app, environment={"SURFSENSE_PLUGIN_SECRET_TOKEN": "s3cret"}
    )

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "s3cret\n"


def test_a_secret_not_in_the_environment_is_asked_for_and_kept_nowhere(
    cli, plugin, real_app
) -> None:
    """Asked for by its title, never a flag, so it stays out of shell history."""
    _declaring_a_token(plugin)

    finished = _invoke(cli, plugin, real_app, typed="s3cret\n")

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "s3cret\n"
    assert "API token" in finished.stderr
    written = [path for path in plugin.folder.rglob("*") if path.is_file()]
    assert not any(b"s3cret" in path.read_bytes() for path in written)
