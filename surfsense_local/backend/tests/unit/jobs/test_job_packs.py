"""A job pack installs from a folder or a .zip only when every file matches its manifest."""

import json
from pathlib import Path

import pytest

from modules.jobs.packs.install import install_pack, remove_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.packs.seal import seal_pack, zip_pack

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
