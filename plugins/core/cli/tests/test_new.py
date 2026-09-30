import pytest
from surfsense_plugin_manifest import load_manifest


@pytest.mark.unit
def test_new_lays_out_a_plugin_that_passes_the_manifest_rules(cli, tmp_path) -> None:
    """A valid start, with its code in a package named after the plugin."""
    folder = tmp_path / "plugins" / "hn-search"

    finished = cli("new", str(folder))

    assert finished.returncode == 0, finished.stderr
    manifest = load_manifest(folder / "manifest.json")
    assert (manifest.id, manifest.access, manifest.hosts) == ("hn-search", "free", [])
    assert (folder / "main.py").is_file()
    assert (folder / "hn_search" / "__init__.py").is_file()


@pytest.mark.unit
def test_new_says_how_to_try_the_plugin(cli, tmp_path) -> None:
    """The next step, ready to copy."""
    finished = cli("new", str(tmp_path / "plugins" / "hn-search"))

    assert "surfsense-plugins invoke hn-search add-note --input text=" in (
        finished.stdout
    )


@pytest.mark.unit
def test_new_signs_the_plugin_with_the_authors_git_name(cli, tmp_path, home) -> None:
    """The author field, filled from who the author already is."""
    (home / ".gitconfig").write_text("[user]\n\tname = Ada Lovelace\n")
    folder = tmp_path / "plugins" / "hn-search"

    cli("new", str(folder))

    assert load_manifest(folder / "manifest.json").author == "Ada Lovelace"


@pytest.mark.app
def test_a_new_plugin_runs_with_invoke_unchanged(cli, tmp_path, real_app) -> None:
    """Nothing to fix before the first run."""
    folder = tmp_path / "plugins" / "hn-search"
    cli("new", str(folder))
    workspace = real_app.new_workspace()

    finished = cli(
        "invoke",
        str(folder),
        "add-note",
        "--input",
        "text=hi",
        "--api-url",
        real_app.url,
        "--workspace",
        str(workspace),
    )

    assert finished.returncode == 0, finished.stderr
    [note] = real_app.call("GET", f"/workspaces/{workspace}/documents")
    assert note["title"] == "Note"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("HN Search", 'must be lowercase letters, digits and "-"'),
        ("core", "core is reserved for SurfSense's own plugins"),
        ("surfsense-scraper", "surfsense-scraper is reserved for SurfSense's own"),
    ],
)
def test_new_refuses_an_id_it_cannot_take(
    cli, tmp_path, name: str, reason: str
) -> None:
    """Refused before anything is written, with the rule it breaks."""
    folder = tmp_path / "plugins" / name

    finished = cli("new", str(folder))

    assert finished.returncode == 1
    assert reason in finished.stderr
    assert not folder.exists()


@pytest.mark.unit
def test_new_never_writes_over_a_plugin_that_exists(cli, tmp_path) -> None:
    """An author's work is never replaced by a template."""
    folder = tmp_path / "plugins" / "hn-search"
    folder.mkdir(parents=True)
    (folder / "main.py").write_text("# mine\n")

    finished = cli("new", str(folder))

    assert finished.returncode == 1
    assert "hn-search already exists" in finished.stderr
    assert (folder / "main.py").read_text() == "# mine\n"


@pytest.mark.unit
def test_new_works_on_a_machine_without_git(cli, tmp_path) -> None:
    """The author field is left to fill in, rather than new failing."""
    folder = tmp_path / "plugins" / "hn-search"

    finished = cli("new", str(folder), environment={"PATH": ""})

    assert finished.returncode == 0, finished.stderr
    assert load_manifest(folder / "manifest.json").author == ""
