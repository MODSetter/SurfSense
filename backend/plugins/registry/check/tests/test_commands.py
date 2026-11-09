"""The commands CI runs: exit status and what they say."""

from registry_check.__main__ import main
from tests.registry_files import valid_entry, write_registry


def test_static_fails_naming_each_problem(tmp_path, capsys):
    registry, first_party = write_registry(tmp_path, [valid_entry(kind="bundle")])
    code = main(
        ["static", "--registry", str(registry), "--first-party", str(first_party)]
    )
    assert code == 1
    assert 'plugins[0] "acme": kind: must be remote' in capsys.readouterr().err


def test_static_passes_a_valid_list(tmp_path):
    registry, first_party = write_registry(tmp_path, [valid_entry()])
    code = main(
        ["static", "--registry", str(registry), "--first-party", str(first_party)]
    )
    assert code == 0


def test_sign_without_a_key_fails_without_touching_the_list(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("REGISTRY_SIGNING_KEY", raising=False)
    registry, _ = write_registry(tmp_path, [valid_entry()])
    before = registry.read_bytes()
    assert main(["sign", "--registry", str(registry)]) == 1
    assert "REGISTRY_SIGNING_KEY" in capsys.readouterr().err
    assert registry.read_bytes() == before


def test_sign_writes_the_published_copy_that_verify_reads(tmp_path, monkeypatch):
    from tests.test_signing import new_key

    private, public = new_key()
    monkeypatch.setenv("REGISTRY_SIGNING_KEY", private)
    registry, _ = write_registry(tmp_path, [valid_entry()])
    published = tmp_path / "published"
    assert (
        main(["sign", "--registry", str(registry), "--published", str(published)]) == 0
    )
    assert (published / "plugins.json.sig").is_file()
    signed = str(published / "plugins.json")
    assert main(["verify", "--registry", signed, "--public-key", public]) == 0
