import pytest

pytestmark = pytest.mark.unit


def test_the_named_action_runs_with_its_inputs(plugin) -> None:
    """The app names an action and writes its inputs; the function gets them by name."""
    plugin.write(
        """
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print(f"echo: {text}")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "echo: hi\n"


def test_an_optional_input_left_empty_arrives_as_none(plugin) -> None:
    """The app leaves an unset input out of the file; the function still gets it."""
    plugin.write(
        """
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str | None) -> None:
    print(f"echo: {text}")
"""
    )

    finished = plugin.run("echo", {})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "echo: None\n"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (
            'raise RuntimeError("the source is down")',
            "RuntimeError: the source is down",
        ),
        ('sys.exit("Token expired")', "Token expired"),
    ],
)
def test_an_action_that_fails_exits_non_zero_with_its_reason(
    plugin, body: str, reason: str
) -> None:
    """The user reads why a run failed in its log, which is the plugin's stderr."""
    plugin.write(
        f"""
import sys

from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    {body}
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert reason in finished.stderr


def test_an_action_the_manifest_does_not_declare_is_refused_by_name(plugin) -> None:
    """A name the plugin never declared fails with that name, not a traceback."""
    plugin.write("")

    finished = plugin.run("missing")

    assert finished.returncode != 0
    assert 'example has no action named "missing"' in finished.stderr
    assert "Traceback" not in finished.stderr


def test_a_declared_action_with_no_function_says_what_is_missing(plugin) -> None:
    """An author who declared an action but forgot to mark its function is told how."""
    plugin.write("def echo(text: str) -> None: ...")

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode != 0
    assert 'mark its function with @action("echo")' in finished.stderr
    assert "Traceback" not in finished.stderr


def test_main_imports_the_plugins_own_package(plugin) -> None:
    """A plugin may split its code into a package beside main.py."""
    plugin.write(
        """
from example_tools.shout import shout
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print(shout(text))
""",
        files={
            "example_tools/__init__.py": "",
            "example_tools/shout.py": "def shout(text):\n    return text.upper()\n",
        },
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "HI\n"


def test_a_plugin_module_named_like_the_standard_library_does_not_replace_it(
    plugin,
) -> None:
    """The plugin's folder comes after the standard library, so csv stays Python's."""
    plugin.write(
        """
import csv

from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print(hasattr(csv, "writer"))
""",
        files={"csv.py": "SHADOWED = True\n"},
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "True\n"


def test_dependencies_import_from_site_packages_and_their_pth_files_run(
    plugin,
) -> None:
    """Packaging installs dependencies there; some, like pywin32, need their .pth."""
    plugin.write(
        """
import pinned
import through_pth
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print(pinned.NAME, through_pth.NAME)
""",
        files={
            "site-packages/pinned.py": 'NAME = "pinned"\n',
            "site-packages/extra.pth": "extra\n",
            "site-packages/extra/through_pth.py": 'NAME = "through_pth"\n',
        },
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "pinned through_pth\n"


def test_an_action_marked_on_two_functions_is_refused(plugin) -> None:
    """Otherwise the second would silently replace the first."""
    plugin.write(
        """
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print("first")


@action("echo")
def echo_again(text: str) -> None:
    print("second")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert finished.stdout == ""
    assert '@action("echo") is on two functions: echo and echo_again' in (
        finished.stderr
    )


def test_a_plugin_without_main_py_says_so(plugin) -> None:
    """An author running by hand is told what is missing, not shown a traceback."""
    plugin.write("")
    (plugin.folder / "main.py").unlink()

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert f"main.py is missing from {plugin.folder}" in finished.stderr
    assert "Traceback" not in finished.stderr
