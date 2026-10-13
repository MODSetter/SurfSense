import hashlib
import platform
import sys

import pytest

IMPORTS_TINYLIB = """
import tinylib
from surfsense_plugin_sdk import action


@action("echo")
def echo(text: str) -> None:
    print(tinylib.NAME)
"""


def _pin(plugin, wheel, name: str, version: str) -> None:
    """requirements.txt as pin-dependencies writes it: exact, with the file's hash."""
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (plugin.folder / "requirements.txt").write_text(
        f"{name}=={version} \\\n    --hash=sha256:{digest}\n"
    )


def _tinylib(plugin, wheels, tag: str = "py3-none-any") -> None:
    """The plugin, depending on a one-module library built for these platforms."""
    wheel = wheels.make(
        "surfsense-test-tinylib", "1.0", {"tinylib.py": 'NAME = "tinylib"\n'}, tag=tag
    )
    plugin.write(IMPORTS_TINYLIB)
    _pin(plugin, wheel, "surfsense-test-tinylib", "1.0")


def _invoke(cli, plugin, wheels, real_app=None):
    """Invoke the plugin with uv pointed at the test's wheels only."""
    app = (
        ["--api-url", real_app.url, "--workspace", str(real_app.new_workspace())]
        if real_app
        else []
    )
    return cli(
        "invoke",
        str(plugin.folder),
        "echo",
        "--input",
        "text=hi",
        *app,
        environment=wheels.environment,
    )


@pytest.mark.app
def test_a_pinned_dependency_is_installed_for_this_machine_and_imported(
    cli, plugin, wheels, real_app
) -> None:
    """Installed beside the plugin, the way a release installs it for each system."""
    _tinylib(plugin, wheels)

    finished = _invoke(cli, plugin, wheels, real_app)

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "tinylib\n"
    assert (plugin.folder / "site-packages" / "tinylib.py").is_file()
    assert f"Installing dependencies for {_this_platform()}" in finished.stderr


@pytest.mark.app
def test_an_unchanged_list_of_dependencies_is_not_installed_again(
    cli, plugin, wheels, real_app
) -> None:
    """Trying a change should take the time of the run, not of an install."""
    _tinylib(plugin, wheels)
    _invoke(cli, plugin, wheels, real_app)
    left_by_the_author = plugin.folder / "site-packages" / "left-alone.txt"
    left_by_the_author.write_text("still here")

    finished = _invoke(cli, plugin, wheels, real_app)

    assert finished.returncode == 0, finished.stderr
    assert left_by_the_author.is_file()
    assert "Installing dependencies" not in finished.stderr


def _another_platform() -> str:
    """A wheel tag for a system this test is not running on."""
    if sys.platform == "win32":
        return "cp312-cp312-manylinux_2_17_x86_64"
    return "cp312-cp312-win_amd64"


def _this_platform() -> str:
    """This machine's key, as plugins/bundles/core/build-targets.json names it."""
    arm = platform.machine().lower() in ("arm64", "aarch64")
    system = {"linux": "linux", "darwin": "macos", "win32": "windows"}[sys.platform]
    return f"{system}-{'arm64' if arm else 'x64'}"


@pytest.mark.unit
def test_a_dependency_with_no_wheel_for_this_machine_is_refused(
    cli, plugin, wheels
) -> None:
    """Named with the platform, since invoke only ever installs for this one."""
    _tinylib(plugin, wheels, tag=_another_platform())

    finished = _invoke(cli, plugin, wheels)

    assert finished.returncode == 1
    assert "surfsense-test-tinylib" in finished.stderr
    assert f"for {_this_platform()}" in finished.stderr
    assert finished.stdout == ""
