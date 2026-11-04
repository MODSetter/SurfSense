"""A job pack installs from a folder or a .zip only when SurfSense signed it and every file
matches its manifest, one install at a time, and a reader always finds a version of it."""

import json
import os
import threading
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import find_job, installed_packs
from modules.jobs.packs.manifest import PackManifest, PackRefusedError, version_key
from modules.jobs.packs.seal import seal_pack, zip_pack
from tests.job_pack_samples import sign_pack

pytestmark = pytest.mark.unit


def write_pack(
    folder: Path,
    *,
    version: str = "1.0.0",
    access: str = "paid",
    pack_id: str = "acme-jobs",
    description: str = "Fills things.",
) -> Path:
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
        "id": pack_id,
        "version": version,
        "name": "Acme jobs",
        "publisher": "Acme",
        "description": description,
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


@pytest.mark.parametrize(
    "runner",
    [
        pytest.param("workbook-rows", id="no version"),
        pytest.param("workbook-rows/0", id="version 0"),
        pytest.param("workbook-rows/1.0", id="a dotted version"),
        pytest.param("workbook-rows/1000000", id="a seven-digit version"),
        pytest.param("workbook-rows/\u0661", id="a digit that is not ASCII"),
        pytest.param("Workbook-rows/1", id="a capital"),
        pytest.param("workbook-rows/1/2", id="two versions"),
    ],
)
def test_a_runner_that_is_not_a_name_and_a_version_is_a_bad_manifest(tmp_path, runner):
    """Contract 6's runner pattern, as the license server holds a pack to it: no app has a
    runner named otherwise, so a newer one would not help."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["jobs"][0]["runner"] = runner
    (pack / "job-pack.json").write_text(json.dumps(manifest))

    with pytest.raises(PackRefusedError) as refused:
        install_pack(pack, tmp_path / "installed")

    assert (refused.value.code, refused.value.message) == (
        "BAD_MANIFEST",
        "Job fill's runner is a name and a version, like workbook-rows/1.",
    )


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


@pytest.mark.parametrize(
    "version",
    [
        "1.0.1234567890",
        "1234567890.0.0",
        "1.0",
        "1.0.0.0",
        "1.0.x",
        # Python's \d takes any script's digits, which no header can carry.
        "1.0.\u0661",
    ],
)
def test_a_version_is_three_parts_of_one_to_nine_digits(tmp_path, version):
    """Contract 6's rule: the app sends the version back as installed_version, which the
    license server takes at one to nine ASCII digits a part, so a longer part, or a digit
    of another script, is no version."""
    pack = write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "job-pack.json").read_text())
    manifest["version"] = version
    (pack / "job-pack.json").write_text(json.dumps(manifest))
    sign_pack(pack)

    assert _refused(pack, tmp_path / "installed") == "BAD_MANIFEST"


def test_a_version_of_nine_digits_a_part_installs(tmp_path):
    """The longest version the rule takes, compared as three integers."""
    version = "999999999.999999999.999999999"

    assert install_pack(write_pack(tmp_path / "pack", version=version), tmp_path / "a")
    assert version_key(version) == (999_999_999,) * 3


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


def _versions(root: Path) -> list[str]:
    return [p.manifest.version for p in installed_packs(root)]


def _on_disk(root: Path, pack_id: str = "acme-jobs") -> list[str]:
    return sorted(p.name for p in (root / pack_id).iterdir())


def _scratch(root: Path) -> list[str]:
    return [p.name for p in root.iterdir() if p.name.startswith(".")]


def test_a_version_is_listed_at_every_moment_of_an_install(tmp_path):
    """Read while installs come and go, the pack is always listed: the new version is in place
    before the old one leaves, and a reader that meets a version gone looks again."""
    root = tmp_path / "installed"
    sources = [
        write_pack(tmp_path / "v1"),
        write_pack(tmp_path / "v2", version="1.1.0"),
    ]
    install_pack(sources[0], root)
    seen: list[list[str]] = []
    done = threading.Event()

    def read() -> None:
        while not done.is_set():
            seen.append(_versions(root))

    reader = threading.Thread(target=read)
    reader.start()
    try:
        for n in range(20):
            install_pack(sources[(n + 1) % 2], root)
    finally:
        done.set()
        reader.join()

    assert seen
    assert [listed for listed in seen if len(listed) != 1] == []


def test_an_old_version_that_cannot_be_moved_stays_and_the_newest_is_listed(
    tmp_path, monkeypatch, caplog
):
    """On Windows a reader holding one of its files open stops the old version moving: it
    stays until the next install, and meanwhile only the newest is listed."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "v1"), root)
    newer = write_pack(tmp_path / "v2", version="1.1.0")
    rename = Path.rename

    def held_open(self: Path, target: Path) -> Path:
        if Path(target).name.startswith(".replaced-"):
            raise PermissionError(13, "The file is in use by another process")
        return rename(self, target)

    monkeypatch.setattr(Path, "rename", held_open)
    install_pack(newer, root)

    assert _on_disk(root) == ["1.0.0", "1.1.0"]
    assert _versions(root) == ["1.1.0"]
    assert "left for the next install" in caplog.text

    monkeypatch.setattr(Path, "rename", rename)
    install_pack(newer, root)

    assert _on_disk(root) == ["1.1.0"]


def test_a_refused_acceptance_leaves_the_installed_version_and_no_scratch(tmp_path):
    """The caller's own rules see the installed versions and run before anything moves."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "v1"), root)
    shown: list[list[str]] = []

    def refuse(new: PackManifest, installed: list[PackManifest]) -> None:
        shown.append([pack.version for pack in installed])
        raise PackRefusedError("PACK_IN_USE", "A run of Acme jobs is under way.")

    with pytest.raises(PackRefusedError):
        install_pack(write_pack(tmp_path / "v2", version="1.1.0"), root, accept=refuse)

    assert shown == [["1.0.0"]]
    assert _versions(root) == ["1.0.0"]
    assert _scratch(root) == []


def test_the_same_signed_pack_again_moves_nothing(tmp_path):
    """Importing the pack already installed leaves its folder as it was."""
    root = tmp_path / "installed"
    pack = write_pack(tmp_path / "pack")
    install_pack(pack, root)
    folder = root / "acme-jobs" / "1.0.0"
    os.utime(folder, (1_000_000_000, 1_000_000_000))
    before = folder.stat()

    assert install_pack(pack, root).version == "1.0.0"

    after = folder.stat()
    assert (after.st_ino, after.st_mtime) == (before.st_ino, before.st_mtime)
    assert _scratch(root) == []


def test_other_contents_at_an_installed_version_are_refused_unless_replacing(tmp_path):
    """A version names one set of bytes; only a developer's paths replace it in place."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "pack"), root)
    other = write_pack(tmp_path / "other", description="Fills other things.")

    with pytest.raises(PackRefusedError) as refused:
        install_pack(other, root)

    assert refused.value.code == "PACK_VERSION_TAKEN"
    assert installed_packs(root)[0].manifest.description == "Fills things."

    install_pack(other, root, replace_same_version=True)

    assert installed_packs(root)[0].manifest.description == "Fills other things."
    assert _scratch(root) == []


def test_an_installed_copy_that_fails_its_checks_is_replaced(tmp_path):
    """No reader lists a copy changed on disk, so the same version installs over it."""
    root = tmp_path / "installed"
    pack = write_pack(tmp_path / "pack")
    install_pack(pack, root)
    (root / "acme-jobs" / "1.0.0" / "jobs/fill/job.json").write_text('{"answers": 1}')

    install_pack(pack, root)

    assert _versions(root) == ["1.0.0"]


def test_installs_are_one_at_a_time(tmp_path):
    """Two installs at once never interleave: each runs its checks and moves its files while
    the other waits, and one version is left."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "v1"), root)
    sources = [
        write_pack(tmp_path / "v2", version="1.1.0"),
        write_pack(tmp_path / "v3", version="1.2.0"),
    ]
    inside: list[str] = []
    most: list[int] = []
    failed: list[BaseException] = []
    count = threading.Lock()

    def slow(new: PackManifest, _installed: list[PackManifest]) -> None:
        with count:
            inside.append(new.version)
            most.append(len(inside))
        time.sleep(0.2)
        with count:
            inside.remove(new.version)

    def install(source: Path) -> None:
        try:
            install_pack(source, root, accept=slow)
        except BaseException as error:
            failed.append(error)

    threads = [threading.Thread(target=install, args=(s,)) for s in sources]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failed == []
    assert max(most) == 1
    assert len(_on_disk(root)) == 1
    assert _scratch(root) == []


def test_leftovers_older_than_an_hour_are_swept(tmp_path):
    """Scratch an install, a download or an import left when the app stopped goes with the
    next install; one still in use, newer than that, stays."""
    root = tmp_path / "installed"
    for folder in (".installing-stale", ".replaced-stale"):
        (root / folder / "pack").mkdir(parents=True)
        (root / folder / "pack" / "job-pack.json").write_text("{}")
    for name in (".download-stale.zip", ".upload-stale.zip", ".download-fresh.zip"):
        (root / name).write_bytes(b"PK")
    hours_ago = time.time() - 2 * 3600
    for stale in root.glob(".*-stale*"):
        os.utime(stale, (hours_ago, hours_ago))

    install_pack(write_pack(tmp_path / "pack"), root)

    assert sorted(p.name for p in root.iterdir()) == [
        ".download-fresh.zip",
        "acme-jobs",
    ]


def test_versions_are_ordered_by_number():
    """0.10.0 comes after 0.9.0, as the server compares them."""
    assert sorted(["1.0.0", "0.10.0", "0.9.10", "0.9.0"], key=version_key) == [
        "0.9.0",
        "0.9.10",
        "0.10.0",
        "1.0.0",
    ]


def test_a_job_is_found_in_the_highest_version_holding_it(tmp_path):
    """A second pack id with the same job, imported by hand, is listed beside the first, and
    the highest version runs."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "a", version="1.4.0"), root)
    install_pack(write_pack(tmp_path / "b", pack_id="bolt-jobs", version="2.0.0"), root)

    pack, job = find_job("fill", root)

    assert [p.manifest.id for p in installed_packs(root)] == ["acme-jobs", "bolt-jobs"]
    assert (pack.manifest.id, pack.manifest.version, job.key) == (
        "bolt-jobs",
        "2.0.0",
        "fill",
    )


def test_a_version_that_vanishes_mid_read_is_read_again(tmp_path, monkeypatch):
    """An install moves the old version away between the listing and its reading: the reader
    lists the pack once more and finds the new version, already in its place."""
    root = tmp_path / "installed"
    install_pack(write_pack(tmp_path / "v1"), root)
    newer = write_pack(tmp_path / "v2", version="1.1.0")
    read_text = Path.read_text
    raced: list[bool] = []

    def install_meanwhile(self: Path, *args, **kwargs) -> str:
        if self.parent == root / "acme-jobs" / "1.0.0" and not raced:
            raced.append(True)
            install_pack(newer, root)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", install_meanwhile)

    assert _versions(root) == ["1.1.0"]
    assert raced == [True]
