import pytest

pytestmark = pytest.mark.unit

READS_TOKEN = """
from surfsense_plugin_sdk import action, secret


@action("echo")
def echo(text: str) -> None:
    print(secret("token"))
"""


def _declaring_token(plugin) -> None:
    """Declares the secret the test plugin reads."""
    plugin.manifest["secrets"] = [{"name": "token", "title": "API token"}]


def test_a_declared_secret_is_read_from_the_environment_the_app_set(plugin) -> None:
    """Secrets travel only in the environment, never in a file."""
    _declaring_token(plugin)
    plugin.write(READS_TOKEN)

    finished = plugin.run(
        "echo", {"text": "hi"}, context={"SURFSENSE_PLUGIN_SECRET_TOKEN": "s3cret"}
    )

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "s3cret\n"


def test_a_secret_the_manifest_does_not_declare_is_refused_by_name(plugin) -> None:
    """The app only hands over declared secrets, so reading another is a bug."""
    plugin.write(READS_TOKEN)

    finished = plugin.run(
        "echo", {"text": "hi"}, context={"SURFSENSE_PLUGIN_SECRET_TOKEN": "s3cret"}
    )

    assert finished.returncode == 1
    assert 'secret "token" is not declared' in finished.stderr
    assert "s3cret" not in finished.stdout


def test_a_declared_secret_with_no_value_is_refused_by_name(plugin) -> None:
    """Refused by name rather than read as empty, so the plugin fails legibly."""
    _declaring_token(plugin)
    plugin.write(READS_TOKEN)

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert 'secret "token" has no value' in finished.stderr
    assert "SURFSENSE_PLUGIN_SECRET_TOKEN" in finished.stderr
