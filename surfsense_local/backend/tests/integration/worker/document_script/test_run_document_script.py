"""A document script runs in its own process and hands back the file it wrote.

Each test starts the real child through worker.py, as the Studio job will.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from shared import cancellation
from worker.document_script.run import run_document_script

pytestmark = pytest.mark.integration

# What the child may see of the parent's environment; anything else is a leak.
ALLOWED_FROM_PARENT = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "LANG",
}
# What the runner sets for every script, whatever the parent had.
CONTRACT = {
    "OUTPUT_PATH",
    "IMAGES_DIR",
    "MPLBACKEND",
    "MPLCONFIGDIR",
    "PYTHONUTF8",
    "PYTHONDONTWRITEBYTECODE",
}


BACKEND = Path(__file__).resolve().parents[4]


def _names_a_process_gives_itself() -> set[str]:
    """What a Python started with only the allowed names has besides them.

    macOS and the interpreter add `__CF_USER_TEXT_ENCODING` and `LC_CTYPE` to
    every process; the parent has them for the same reason, not as their source.
    """
    allowed = {
        name: value
        for name, value in os.environ.items()
        if name.upper() in ALLOWED_FROM_PARENT
    }
    listed = subprocess.run(
        [sys.executable, "-c", "import json, os; print(json.dumps(list(os.environ)))"],
        env=allowed,
        capture_output=True,
        text=True,
        check=True,
    )
    return {name.upper() for name in json.loads(listed.stdout)} - ALLOWED_FROM_PARENT


# A worker that runs one script, for a test to kill midway.
WORKER_RUNNING_A_SCRIPT = """
import sys
from worker.document_script.run import run_document_script

run_document_script(sys.argv[1], output_name="document.pdf", images={})
"""


def _scripts_root(data_dir: Path) -> Path:
    return data_dir / "tmp" / "document-scripts"


def _starts_a_helper_then(pids: Path, then: str) -> str:
    """A script that starts a minute-long helper, notes both pids, then runs `then`."""
    return (
        "import os, subprocess, sys, time\n"
        "helper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pids)!r}, 'w').write(f'{{os.getpid()}} {{helper.pid}}')\n"
        f"{then}\n"
    )


def _pids(pids: Path) -> tuple[int, int]:
    script_pid, helper_pid = (int(pid) for pid in pids.read_text().split())
    return script_pid, helper_pid


def _all_gone_within(seconds: float, *pids: int) -> bool:
    deadline = time.monotonic() + seconds
    while any(psutil.pid_exists(pid) for pid in pids):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


def test_a_script_that_writes_output_path_returns_its_bytes() -> None:
    """The happy path: exit 0 and a non-empty file is a result with those bytes."""
    script = (
        "import os\n"
        "with open(os.environ['OUTPUT_PATH'], 'wb') as out:\n"
        "    out.write(b'hello')\n"
    )

    result = run_document_script(script, output_name="document.pdf", images={})

    assert result.ok
    assert result.output == b"hello"
    assert result.error is None
    assert result.traceback_tail is None
    assert result.seconds > 0


def test_a_script_that_raises_returns_its_error_and_traceback() -> None:
    """The model fixes its script from the error line and the frames in its file."""
    script = "def build():\n    raise ValueError('no table rows')\n\nbuild()\n"

    result = run_document_script(script, output_name="document.docx", images={})

    assert not result.ok
    assert result.output is None
    assert result.error == "ValueError: no table rows"
    assert result.traceback_tail is not None
    assert 'script.py", line 2, in build' in result.traceback_tail
    # The runner's own frames are noise to the model.
    assert "runpy" not in result.traceback_tail


def test_a_traceback_names_the_script_without_its_run_folder(data_dir: Path) -> None:
    """The folder is gone once the run ends, and its absolute path in every frame
    would crowd the traceback's lines out of the stored reason."""
    script = "def build():\n    raise ValueError('no table rows')\n\nbuild()\n"

    result = run_document_script(script, output_name="document.docx", images={})

    assert result.traceback_tail is not None
    assert 'File "script.py", line 2, in build' in result.traceback_tail
    assert _scripts_root(data_dir).name not in result.traceback_tail


def test_a_syntax_error_names_itself() -> None:
    """A script that does not compile fails with the SyntaxError, not a crash."""
    result = run_document_script(
        "def broken(:\n    pass\n", output_name="document.docx", images={}
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.startswith("SyntaxError: ")
    assert result.traceback_tail is not None
    assert "line 1" in result.traceback_tail


def test_a_script_that_exits_cleanly_without_a_file_is_a_failure() -> None:
    """Exit 0 is not success on its own: the document is the file. What the
    script printed to stderr is kept, since it may say why."""
    script = "import sys\nprint('saved to the wrong place', file=sys.stderr)\n"

    result = run_document_script(script, output_name="document.pdf", images={})

    assert not result.ok
    assert result.output is None
    assert result.error == "the script wrote no file at OUTPUT_PATH"
    assert result.traceback_tail == "saved to the wrong place"


def test_an_empty_output_file_is_a_failure() -> None:
    """An empty file opens as nothing in Studio, so it is not a document."""
    script = "import os\nopen(os.environ['OUTPUT_PATH'], 'wb').close()\n"

    result = run_document_script(script, output_name="document.pdf", images={})

    assert not result.ok
    assert result.error == "the script wrote an empty file at OUTPUT_PATH"


def test_a_script_past_its_timeout_is_killed_with_every_process_it_started(
    tmp_path: Path, data_dir: Path
) -> None:
    """A thread cannot be stopped; a process tree can, and nothing outlives it."""
    pids = tmp_path / "pids.txt"
    script = _starts_a_helper_then(pids, "time.sleep(60)")

    started = time.monotonic()
    result = run_document_script(
        script, output_name="document.pdf", images={}, timeout_seconds=2
    )
    elapsed = time.monotonic() - started

    assert not result.ok
    assert result.error == "timed out after 2 s"
    assert elapsed < 15
    script_pid, helper_pid = _pids(pids)
    assert not psutil.pid_exists(script_pid)
    assert not psutil.pid_exists(helper_pid)
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_a_helper_the_script_leaves_running_does_not_hold_up_its_result(
    tmp_path: Path, data_dir: Path
) -> None:
    """The run ends when the script does: a helper that inherited its output
    is killed then, and the folder it was working in is removed."""
    pids = tmp_path / "pids.txt"
    script = _starts_a_helper_then(
        pids, "open(os.environ['OUTPUT_PATH'], 'wb').write(b'built')"
    )

    started = time.monotonic()
    result = run_document_script(
        script, output_name="document.pdf", images={}, timeout_seconds=30
    )
    elapsed = time.monotonic() - started

    assert result.ok, result.error
    assert result.output == b"built"
    assert elapsed < 15
    assert not psutil.pid_exists(_pids(pids)[1])
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_a_cancelled_job_stops_its_script_without_waiting_out_the_limit(
    tmp_path: Path, data_dir: Path
) -> None:
    """The tree is killed and the job's own cancel error comes through."""
    pids = tmp_path / "pids.txt"
    script = _starts_a_helper_then(pids, "time.sleep(60)")

    class CancelledError(Exception):
        pass

    def cancel_once_running() -> None:
        if pids.exists() and pids.read_text():
            raise CancelledError

    started = time.monotonic()
    with cancellation.watching(cancel_once_running), pytest.raises(CancelledError):
        run_document_script(
            script, output_name="document.pdf", images={}, timeout_seconds=60
        )
    elapsed = time.monotonic() - started

    assert elapsed < 15
    assert _all_gone_within(5, *_pids(pids))
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_a_worker_that_dies_mid_run_takes_the_script_and_its_helpers_with_it(
    tmp_path: Path, data_dir: Path
) -> None:
    """Nothing a script started outlives the worker that ran it."""
    pids = tmp_path / "pids.txt"
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            WORKER_RUNNING_A_SCRIPT,
            _starts_a_helper_then(pids, "time.sleep(60)"),
        ],
        cwd=BACKEND,
        env={**os.environ, "SURFSENSE_LOCAL_DATA_DIR": str(data_dir)},
    )
    try:
        deadline = time.monotonic() + 30
        while not (pids.exists() and pids.read_text()):
            assert time.monotonic() < deadline, "the script never started"
            assert worker.poll() is None, "the worker exited before the script ran"
            time.sleep(0.1)
    finally:
        worker.kill()
        worker.wait()

    assert _all_gone_within(5, *_pids(pids))


def test_the_child_sees_none_of_the_parents_secrets(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    """A script is model-written: it gets the contract and the OS basics, no keys."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-parent")
    monkeypatch.setenv("OPENCODE_SERVER_PASSWORD", "parent-password")
    script = (
        "import json, os\n"
        "with open(os.environ['OUTPUT_PATH'], 'w') as out:\n"
        "    json.dump(dict(os.environ), out)\n"
    )

    result = run_document_script(script, output_name="env.json", images={})

    assert result.ok and result.output is not None
    seen = {name.upper(): value for name, value in json.loads(result.output).items()}
    passed_on = ALLOWED_FROM_PARENT | CONTRACT | _names_a_process_gives_itself()
    leaked = {
        name
        for name in os.environ
        if name.upper() not in passed_on and name.upper() in seen
    }
    assert leaked == set()
    folder = Path(seen["OUTPUT_PATH"]).parent
    assert folder.parent == _scripts_root(data_dir)
    assert seen["OUTPUT_PATH"] == str(folder / "env.json")
    assert seen["IMAGES_DIR"] == str(folder / "images")
    assert seen["MPLBACKEND"] == "Agg"
    assert seen["PYTHONUTF8"] == "1"


def test_the_child_loads_none_of_the_workers_queue_or_database() -> None:
    """Script mode starts before the consumer's imports: no Huey, no DB, no settings."""
    script = (
        "import os, sys\n"
        "with open(os.environ['OUTPUT_PATH'], 'w') as out:\n"
        "    out.write('\\n'.join(sorted(sys.modules)))\n"
    )

    result = run_document_script(script, output_name="modules.txt", images={})

    assert result.ok and result.output is not None
    loaded = set(result.output.decode().split("\n"))
    forbidden = {"huey", "sqlalchemy", "shared.db", "shared.queue", "shared.config"}
    assert loaded & forbidden == set()
    assert not any(name.startswith("modules.") for name in loaded)


def test_a_script_that_deletes_its_own_file_still_returns_its_output() -> None:
    """The caller keeps the script it passed; the copy on disk is only for running."""
    script = (
        "import os\n"
        "os.remove(__file__)\n"
        "with open(os.environ['OUTPUT_PATH'], 'wb') as out:\n"
        "    out.write(b'made')\n"
    )

    result = run_document_script(script, output_name="document.pdf", images={})

    assert result.ok
    assert result.output == b"made"


def test_the_run_folder_is_removed_afterwards(data_dir: Path) -> None:
    """Every run gets a fresh folder, and none is left behind, success or failure."""
    writes = "import os\nopen(os.environ['OUTPUT_PATH'], 'wb').write(b'x')\n"

    run_document_script(writes, output_name="document.pdf", images={})
    run_document_script("raise SystemExit(3)\n", output_name="a.pdf", images={})

    assert list(_scripts_root(data_dir).iterdir()) == []


def test_an_image_that_cannot_be_copied_leaves_no_folder(
    tmp_path: Path, data_dir: Path
) -> None:
    """A figure gone from disk fails the call before the script runs, cleanly."""
    with pytest.raises(FileNotFoundError):
        run_document_script(
            "x = 1\n",
            output_name="document.pdf",
            images={"12-1": tmp_path / "missing.png"},
        )

    assert list(_scripts_root(data_dir).iterdir()) == []


def test_a_non_zero_exit_without_a_traceback_reports_its_status() -> None:
    """sys.exit(3) prints nothing, so the status is all the model gets."""
    result = run_document_script(
        "raise SystemExit(3)\n", output_name="document.pdf", images={}
    )

    assert not result.ok
    assert result.error == "the script exited with status 3"
    assert result.traceback_tail is None


def test_a_flood_on_stderr_keeps_only_its_tail_in_the_worker() -> None:
    """A runaway script may write gigabytes there; the worker and its other jobs must not hold them."""
    script = (
        "import sys\n"
        "line = 'x' * 1000 + chr(10)\n"
        "for _ in range(200_000):\n"
        "    sys.stderr.write(line)\n"
        "raise ValueError('the last line')\n"
    )
    worker = psutil.Process()
    before = worker.memory_info().rss
    peak, running = [before], [True]

    def sample() -> None:
        while running[0]:
            peak[0] = max(peak[0], worker.memory_info().rss)
            time.sleep(0.01)

    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        result = run_document_script(script, output_name="d.docx", images={})
    finally:
        running[0] = False
        sampler.join()

    assert (peak[0] - before) < 50 * 2**20
    assert result.error == "ValueError: the last line"
    assert "raise ValueError('the last line')" in (result.traceback_tail or "")


def test_only_the_last_thirty_lines_of_stderr_are_kept() -> None:
    """The end of the output explains the failure; the rest is noise to the model."""
    script = (
        "import sys\n"
        "for n in range(100):\n"
        "    print(f'warning {n}', file=sys.stderr)\n"
        "raise RuntimeError('late')\n"
    )

    result = run_document_script(script, output_name="document.pdf", images={})

    assert result.traceback_tail is not None
    lines = result.traceback_tail.splitlines()
    assert len(lines) == 30
    assert lines[-1] == "RuntimeError: late"
    assert "warning 0" not in result.traceback_tail


@pytest.mark.parametrize("name", ["../escape.pdf", "sub/document.pdf", ""])
def test_an_output_name_must_be_a_plain_file_name(name: str) -> None:
    """OUTPUT_PATH stays inside the run folder."""
    with pytest.raises(ValueError):
        run_document_script("x = 1\n", output_name=name, images={})
