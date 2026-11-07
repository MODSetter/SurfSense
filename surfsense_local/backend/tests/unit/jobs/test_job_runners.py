"""Every runner a pack may name has its code in the app, and the redline's pack installs."""

import pytest

from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import RUNNERS
from modules.jobs.runners import BY_NAME, runner_of
from tests.job_pack_samples import REDLINE_JOB, write_contract_pack

pytestmark = pytest.mark.unit


def test_every_runner_a_pack_may_name_has_its_code():
    """Install accepts exactly the runners the app can run, so no installed job lacks one."""
    assert set(BY_NAME) == set(RUNNERS)


def test_a_redline_pack_installs_and_its_job_takes_a_word_contract(tmp_path):
    """A pack naming word-clauses/1 installs, and its job takes a .docx and reads its config."""
    root = tmp_path / "installed"
    install_pack(write_contract_pack(tmp_path / "pack"), root)

    (pack,) = installed_packs(root)
    (job,) = pack.manifest.jobs
    runner = runner_of(job)

    assert (job.key, runner.formats) == (REDLINE_JOB, ("docx",))
    assert [s.key for s in runner.load_config(pack.path(job.config)).settings] == [
        "external_comments"
    ]
