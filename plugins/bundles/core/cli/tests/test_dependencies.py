import pytest

pytestmark = pytest.mark.unit

TINYLIB = "surfsense-test-tinylib"
OTHERLIB = "surfsense-test-otherlib"


def _library(wheels, name: str, version: str = "1.0") -> None:
    """A one-module library the test's wheel folder offers."""
    module = name.rsplit("-", 1)[1]
    wheels.make(name, version, {f"{module}.py": f'NAME = "{module}"\n'})


def _files(plugin) -> tuple[str, str]:
    """requirements.in and requirements.txt, empty when absent."""
    read = [plugin.folder / "requirements.in", plugin.folder / "requirements.txt"]
    return tuple(path.read_text() if path.exists() else "" for path in read)


@pytest.fixture
def written(plugin):
    """The example plugin, with no dependencies yet."""
    plugin.write("from surfsense_plugin_sdk import action\n")
    return plugin


def test_add_lists_the_library_and_pins_it_with_hashes(cli, written, wheels) -> None:
    """The short list for review, and the exact files for every platform."""
    _library(wheels, TINYLIB)

    finished = cli("add", str(written.folder), TINYLIB, environment=wheels.environment)

    assert finished.returncode == 0, finished.stderr
    listed, pinned = _files(written)
    assert listed == f"{TINYLIB}\n"
    assert f"{TINYLIB}==1.0" in pinned
    assert "--hash=sha256:" in pinned
    assert f"Added {TINYLIB}" in finished.stdout
    assert "requirements.txt pins 1 package" in finished.stdout


def test_adding_a_library_keeps_the_versions_already_pinned(
    cli, written, wheels
) -> None:
    """Adding one library upgrades nothing else."""
    _library(wheels, TINYLIB, "1.0")
    cli("add", str(written.folder), TINYLIB, environment=wheels.environment)
    _library(wheels, TINYLIB, "2.0")
    _library(wheels, OTHERLIB)

    finished = cli("add", str(written.folder), OTHERLIB, environment=wheels.environment)

    assert finished.returncode == 0, finished.stderr
    listed, pinned = _files(written)
    assert listed == f"{TINYLIB}\n{OTHERLIB}\n"
    assert f"{TINYLIB}==1.0" in pinned
    assert f"{OTHERLIB}==1.0" in pinned


def test_remove_drops_a_library_from_both_files(cli, written, wheels) -> None:
    """What the plugin no longer imports is no longer installed."""
    _library(wheels, TINYLIB)
    _library(wheels, OTHERLIB)
    cli("add", str(written.folder), TINYLIB, OTHERLIB, environment=wheels.environment)

    finished = cli(
        "remove", str(written.folder), TINYLIB, environment=wheels.environment
    )

    assert finished.returncode == 0, finished.stderr
    listed, pinned = _files(written)
    assert TINYLIB not in listed + pinned
    assert f"{OTHERLIB}==1.0" in pinned
    assert f"Removed {TINYLIB}" in finished.stdout
    assert "requirements.txt pins 1 package" in finished.stdout


def test_removing_the_last_library_removes_both_files(cli, written, wheels) -> None:
    """A plugin with no dependencies has neither file."""
    _library(wheels, TINYLIB)
    cli("add", str(written.folder), TINYLIB, environment=wheels.environment)

    finished = cli(
        "remove", str(written.folder), TINYLIB, environment=wheels.environment
    )

    assert finished.returncode == 0, finished.stderr
    assert not (written.folder / "requirements.in").exists()
    assert not (written.folder / "requirements.txt").exists()
    assert "example has no dependencies left" in finished.stdout


def test_removing_a_library_the_plugin_does_not_list_is_refused(cli, written) -> None:
    """Named, rather than silently doing nothing."""
    finished = cli("remove", str(written.folder), TINYLIB)

    assert finished.returncode == 1
    assert f"example does not list {TINYLIB}" in finished.stderr


def test_adding_a_library_that_cannot_be_found_changes_nothing(
    cli, written, wheels
) -> None:
    """The list stays as it was, so the plugin is never left half pinned."""
    finished = cli(
        "add",
        str(written.folder),
        "surfsense-test-missing",
        environment=wheels.environment,
    )

    assert finished.returncode == 1
    assert "surfsense-test-missing" in finished.stderr
    assert _files(written) == ("", "")


def test_pin_dependencies_pins_again_after_a_hand_edit(cli, written, wheels) -> None:
    """For a version range written by hand, or a platform build-targets.json gains."""
    _library(wheels, TINYLIB)
    (written.folder / "requirements.in").write_text(f"{TINYLIB}>=1\n")

    finished = cli(
        "pin-dependencies", str(written.folder), environment=wheels.environment
    )

    assert finished.returncode == 0, finished.stderr
    listed, pinned = _files(written)
    assert listed == f"{TINYLIB}>=1\n"
    assert f"{TINYLIB}==1.0" in pinned
    assert "requirements.txt pins 1 package" in finished.stdout


def test_the_pinned_file_says_which_command_made_it(cli, written, wheels) -> None:
    """A reader who opens requirements.txt learns how to change it, not to edit it."""
    _library(wheels, TINYLIB)

    cli("add", str(written.folder), TINYLIB, environment=wheels.environment)

    _, pinned = _files(written)
    assert "surfsense-plugins pin-dependencies example" in pinned


def test_a_removal_that_cannot_be_pinned_changes_nothing(cli, written, wheels) -> None:
    """Both files stay as they were, so the plugin is never left half pinned."""
    _library(wheels, TINYLIB)
    _library(wheels, OTHERLIB)
    cli("add", str(written.folder), TINYLIB, OTHERLIB, environment=wheels.environment)
    before = _files(written)
    for wheel in wheels.folder.glob("surfsense_test_otherlib-*.whl"):
        wheel.unlink()

    finished = cli(
        "remove", str(written.folder), TINYLIB, environment=wheels.environment
    )

    assert finished.returncode == 1
    assert "the dependencies cannot be pinned" in finished.stderr
    assert _files(written) == before
