"""A job pack installs from a folder or a .zip only when SurfSense signed it and every file
matches its manifest."""

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.packs.seal import seal_pack, zip_pack
from tests.job_pack_samples import sign_pack

pytestmark = pytest.mark.unit


def write_pack(folder: Path, *, version: str = "1.0.0", access: str = "paid") -> Path:
    """A sealed pack with one job, its config and its skill."""
    files = {
        "LICENSE.md": "Closed licence.",
        "jobs/fill/job.json": json.dumps({"answers": []}),
        "skills/surfsense-job-fill/SKILL.md": "---\nname: surfsense-job-fill\n---\nFill it.",
    }
    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    manifest = {
        "schema": "surfsense-job-pack/1",
        "id": "acme-jobs",
        "version": version,
        "name": "Acme jobs",
        "publisher": "Acme",
        "description": "Fills things.",
        "access": access,
        "license_file": "LICENSE.md",
        "jobs": [
            {
                "key": "fill",
                "name": "Fill",
                "description": "Fills a workbook.",
                "runner": "workbook-rows/1",
                "config": "jobs/fill/job.json",
                "skill": "skills/surfsense-job-fill",
            }
        ],
        "files": {"LICENSE.md": "0" * 64},
    }
    (folder / "job-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    seal_pack(folder)
    sign_pack(folder)
    return folder


def test_a_sealed_folder_installs_and_is_listed(tmp_path):
    """A sealed folder installs, and its job, skill and files are found."""
    pack = write_pack(tmp_path / "pack")
    root = tmp_path / "installed"

    manifest = install_pack(pack, root)

    assert manifest.id == "acme-jobs"
    [listed] = installed_packs(root)
    assert listed.job("fill").skill == "skills/surfsense-job-fill"
    assert listed.path("jobs/fill/job.json").is_file()


def test_a_zipped_pack_installs_whether_or_not_a_folder_wraps_it(tmp_path):
    """The zip the author tool makes installs as the folder does."""
    pack = write_pack(tmp_path / "pack")
    flat = zip_pack(pack, tmp_path / "flat.zip")

    assert install_pack(flat, tmp_path / "a").version == "1.0.0"


@pytest.mark.parametrize(
    ("tamper", "code"),
    [
        (lambda p: (p / "jobs/fill/job.json").write_text("{}"), "PACK_FILE_CHANGED"),
        (lambda p: (p / "extra.md").write_text("hi"), "PACK_FILE_UNLISTED"),
        (lambda p: (p / "LICENSE.md").unlink(), "PACK_FILE_MISSING"),
    ],
)
def test_a_pack_that_differs_from_its_manifest_is_refused_and_nothing_installs(
    tmp_path, tamper, code
):
    """A changed, extra or missing file refuses the whole pack."""
    pack = write_pack(tmp_path / "pack")
    tamper(pack)
    root = tmp_path / "installed"

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, root)

    assert refused.value.code == code
    assert installed_packs(root) == []


def test_a_manifest_naming_a_file_outside_the_pack_is_refused(tmp_path):
    """A path that climbs out of the pack is refused before anything is copied."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["files"]["../outside.md"] = "0" * 64
    (pack / "job-pack.json").write_text(json.dumps(manifest))

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, tmp_path / "installed")

    assert refused.value.code == "BAD_PATH"


def test_a_new_version_replaces_the_old_one_and_removal_empties_the_list(tmp_path):
    """One version per pack stays on disk, and removing the pack leaves none."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "v1"), root)
    install_pack(write_pack(tmp_path / "v2", version="1.1.0"), root)

    assert [p.manifest.version for p in installed_packs(root)] == ["1.1.0"]
    assert remove_pack("acme-jobs", root)
    assert installed_packs(root) == []


def test_an_installed_pack_changed_on_disk_is_left_out(tmp_path):
    """A pack changed after it was installed is no longer offered."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "pack"), root)
    (root / "acme-jobs" / "1.0.0" / "jobs/fill/job.json").write_text('{"answers": 1}')

    assert installed_packs(root) == []


def test_a_job_for_a_runner_this_app_lacks_needs_a_newer_app(tmp_path):
    """A job for a runner this app does not ship says it needs a newer app."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["jobs"][0]["runner"] = "documents-rows/9"
    (pack / "job-pack.json").write_text(json.dumps(manifest))

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, tmp_path / "installed")

    assert refused.value.code == "NEEDS_NEWER_APP"


def _refused(pack: Path, root: Path) -> str:
    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, root)
    assert installed_packs(root) == []
    return refused.value.code


def test_an_unsigned_pack_is_refused(tmp_path):
    """A pack SurfSense did not sign does not install, sealed or not."""
    pack = write_pack(tmp_path / "pack")
    (pack / "job-pack.sig").unlink()

    assert _refused(pack, tmp_path / "installed") == "PACK_NOT_SIGNED"


def test_a_manifest_changed_after_signing_is_refused(tmp_path):
    """A manifest edited after signing, here only its description, breaks the signature."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["description"] = "Fills things, and more."
    (pack / "job-pack.json").write_text(json.dumps(manifest))

    assert _refused(pack, tmp_path / "installed") == "PACK_BAD_SIGNATURE"


def test_a_pack_signed_with_another_key_is_refused(tmp_path):
    """Only a key the app compiles in signs a pack it installs."""
    pack = write_pack(tmp_path / "pack")
    sign_pack(pack, Ed25519PrivateKey.generate())

    assert _refused(pack, tmp_path / "installed") == "PACK_BAD_SIGNATURE"


def test_a_signature_holds_across_line_endings_and_indents(tmp_path):
    """What is signed is the manifest's content, so the manifest rewritten with CRLF line
    endings or another indent stays installable. The other files are checked byte for byte,
    so a pack's repository converts no line endings."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    (pack / "job-pack.json").write_bytes(
        json.dumps(manifest, indent=4).replace("\n", "\r\n").encode()
    )

    assert install_pack(pack, tmp_path / "installed").id == "acme-jobs"


def test_an_installed_pack_that_loses_its_signature_is_left_out(tmp_path):
    """The signature is checked on every read, not only on install."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "pack"), root)
    (root / "acme-jobs" / "1.0.0" / "job-pack.sig").unlink()

    assert installed_packs(root) == []


def test_sealing_a_signed_pack_does_not_list_its_signature(tmp_path):
    """Sealed again, the manifest never lists its own signature as one of the pack's files."""
    pack = write_pack(tmp_path / "pack")

    manifest = seal_pack(pack)

    assert "job-pack.sig" not in manifest["files"]


@pytest.mark.parametrize("entitlement", ["job_fill", "JOB-FILL", "", 7])
def test_a_job_s_entitlement_is_a_licence_code(tmp_path, entitlement):
    """An entitlement is written as the licence server names it, in capitals."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["jobs"][0]["entitlement"] = entitlement
    (pack / "job-pack.json").write_text(json.dumps(manifest))

    assert _refused(pack, tmp_path / "installed") == "BAD_MANIFEST"


def test_a_manifest_edited_after_install_is_left_out(tmp_path):
    """Read again later, a manifest changed on disk breaks its signature though every file
    still matches it."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "pack"), root)
    installed = root / "acme-jobs" / "1.0.0" / "job-pack.json"
    manifest = json.loads(installed.read_text())
    manifest["access"] = "free"
    installed.write_text(json.dumps(manifest))

    assert installed_packs(root) == []


def test_a_manifest_that_cannot_be_signed_is_refused_not_a_crash(tmp_path):
    """A lone surrogate in the manifest cannot be put in signed form: the pack is refused, and
    a listing that meets it on disk leaves it out instead of failing."""
    pack = write_pack(tmp_path / "pack")
    text = (pack / "job-pack.json").read_text()
    (pack / "job-pack.json").write_text(text.replace("Fills things.", "\\ud800"))

    assert _refused(pack, tmp_path / "installed") == "PACK_BAD_SIGNATURE"

    root = tmp_path / "listed"
    install_pack(write_pack(tmp_path / "good"), root)
    (root / "acme-jobs" / "1.0.0" / "job-pack.json").write_text(
        text.replace("Fills things.", "\\ud800")
    )
    assert installed_packs(root) == []


def test_a_pack_signed_by_any_listed_key_installs(tmp_path, monkeypatch):
    """While a key is rotated, a release trusts the new key and the old one."""
    old, new = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    monkeypatch.setattr(
        "modules.jobs.packs.signature.PACK_PUBLIC_KEYS_HEX",
        (_public_hex(new), _public_hex(old)),
    )
    for key in (old, new):
        pack = write_pack(tmp_path / f"pack-{id(key)}")
        sign_pack(pack, key)
        assert install_pack(pack, tmp_path / f"installed-{id(key)}").id == "acme-jobs"

    stranger = write_pack(tmp_path / "stranger")
    sign_pack(stranger, Ed25519PrivateKey.generate())
    assert _refused(stranger, tmp_path / "installed-stranger") == "PACK_BAD_SIGNATURE"


def _public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
