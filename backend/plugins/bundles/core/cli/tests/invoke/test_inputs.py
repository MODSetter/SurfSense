import pytest

PRINTS_ITS_INPUTS = """
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str, top: float | None, loud: bool | None, ratio: float | None) -> None:
    print(type(text).__name__, repr(top), repr(loud), repr(ratio))
"""


def _declaring_every_kind(plugin) -> None:
    """One required text input, and an optional one of every other kind."""
    plugin.manifest["actions"][0]["inputs"] = [
        {"name": "text", "title": "Text", "kind": "string", "required": True},
        {"name": "top", "title": "Top", "kind": "number"},
        {"name": "loud", "title": "Loud", "kind": "boolean"},
        {"name": "ratio", "title": "Ratio", "kind": "number"},
    ]


@pytest.mark.app
def test_inputs_arrive_as_their_declared_kinds(cli, plugin, real_app) -> None:
    """What the author types is text; the plugin gets what its manifest declares."""
    _declaring_every_kind(plugin)
    plugin.write(PRINTS_ITS_INPUTS)

    finished = cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        "--input",
        "top=5",
        "--input",
        "loud=true",
        "--input",
        "ratio=0.5",
        "--api-url",
        real_app.url,
        "--workspace",
        str(real_app.new_workspace()),
    )

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "str 5 True 0.5\n"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        (["text=hi", "colour=red"], 'echo has no input named "colour"'),
        (["text=hi", "top=many"], "top must be a number, not many"),
        (["text=hi", "loud=yes"], "loud must be true or false, not yes"),
        (["top=5"], "text is required: pass --input text=…"),
        (["text"], "text: an input is name=value"),
    ],
)
def test_an_input_the_action_cannot_take_is_refused_before_running(
    cli, plugin, typed: list[str], reason: str
) -> None:
    """Refused as the app's run route refuses it, before any app is involved."""
    _declaring_every_kind(plugin)
    plugin.write(PRINTS_ITS_INPUTS)
    arguments = [part for entry in typed for part in ("--input", entry)]

    finished = cli("invoke", str(plugin.folder), "echo", *arguments)

    assert finished.returncode == 1
    assert reason in finished.stderr
    assert finished.stdout == ""


@pytest.mark.unit
def test_an_action_the_plugin_does_not_declare_is_refused(cli, plugin) -> None:
    """Named plainly, with the actions the plugin does have."""
    plugin.write(PRINTS_ITS_INPUTS)

    finished = cli("invoke", str(plugin.folder), "search", "--input", "text=hi")

    assert finished.returncode == 1
    assert 'example has no action named "search": its actions are echo' in (
        finished.stderr
    )
