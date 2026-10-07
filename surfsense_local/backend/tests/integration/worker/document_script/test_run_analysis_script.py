"""An analysis script runs in the script runner over read-only copies of its inputs and keeps what it saves.

Each test starts the real child through worker.py, as the Studio worker will.
"""

import json
import os
from pathlib import Path

import pytest

from worker.document_script.analysis_run import AnalysisInput, run_analysis_script

pytestmark = pytest.mark.integration

SALES = (
    "month,region,revenue\nJan,North,120\nJan,South,80\nFeb,North,150\nFeb,South,95\n"
)


def _scripts_root(data_dir: Path) -> Path:
    return data_dir / "tmp" / "document-scripts"


def _sales(tmp_path: Path, name: str = "Sales 2026.csv") -> AnalysisInput:
    source = tmp_path / "documents" / "7" / name
    source.parent.mkdir(parents=True)
    source.write_text(SALES, encoding="utf-8")
    return AnalysisInput(path=source, name=name, document_id=7, title="Sales 2026")


def test_a_script_reads_its_input_and_prints_and_saves_a_table_and_a_chart(
    tmp_path: Path, data_dir: Path
) -> None:
    """The model's pandas code sees the file by its name and keeps what it saves in OUTPUT_DIR."""
    sales = _sales(tmp_path)
    keep_in = tmp_path / "kept"
    script = (
        "import os\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "df = pd.read_csv(os.path.join(os.environ['INPUT_DIR'], 'Sales 2026.csv'))\n"
        "totals = df.groupby('month', sort=False)['revenue'].sum()\n"
        "print('total revenue', int(df['revenue'].sum()))\n"
        "out = os.environ['OUTPUT_DIR']\n"
        "totals.to_csv(os.path.join(out, 'totals.csv'))\n"
        "totals.plot(kind='bar')\n"
        "plt.savefig(os.path.join(out, 'revenue by month.png'))\n"
    )

    run = run_analysis_script(script, [sales], keep_in)

    assert run.ok, run.traceback_tail
    assert run.stdout == "total revenue 445\n"
    assert run.stdout_cut == 0
    assert run.error is None
    # A name with a space is made one a document script can place.
    assert run.kept == ("revenue_by_month.png", "totals.csv")
    assert (keep_in / "totals.csv").read_text().splitlines() == [
        "month,revenue",
        "Jan,200",
        "Feb,245",
    ]
    assert (keep_in / "revenue_by_month.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_the_manifest_names_each_input_by_its_source(tmp_path: Path) -> None:
    """The model maps a file back to the source it cites by the manifest."""
    script = (
        "import os\n"
        "print(open(os.path.join(os.environ['INPUT_DIR'], 'manifest.json')).read())\n"
    )

    run = run_analysis_script(script, [_sales(tmp_path)], tmp_path / "kept")

    assert run.ok, run.traceback_tail
    assert json.loads(run.stdout) == [
        {"file": "Sales 2026.csv", "document_id": 7, "title": "Sales 2026"}
    ]


def test_the_source_file_is_never_written(tmp_path: Path, data_dir: Path) -> None:
    """The inputs are read-only copies: a script that forces its way in changes only its copy."""
    sales = _sales(tmp_path)
    before = sales.path.read_bytes(), sales.path.stat().st_mtime_ns
    script = (
        "import os, stat\n"
        "path = os.path.join(os.environ['INPUT_DIR'], 'Sales 2026.csv')\n"
        "try:\n"
        "    open(path, 'a').write('x')\n"
        "except PermissionError:\n"
        "    print('read-only')\n"
        "os.chmod(path, stat.S_IWRITE | stat.S_IREAD)\n"
        "open(path, 'w').write('overwritten')\n"
    )

    run = run_analysis_script(script, [sales], tmp_path / "kept")

    assert run.ok, run.traceback_tail
    assert run.stdout == "read-only\n"
    assert (sales.path.read_bytes(), sales.path.stat().st_mtime_ns) == before
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_read_only_inputs_do_not_leave_the_run_folder_behind(
    tmp_path: Path, data_dir: Path
) -> None:
    """Windows will not delete a read-only file as it is; the folder still goes."""
    run = run_analysis_script("x = 1\n", [_sales(tmp_path)], tmp_path / "kept")

    assert run.ok
    assert list(_scripts_root(data_dir).iterdir()) == []


def test_a_failed_script_keeps_nothing_and_says_why(tmp_path: Path) -> None:
    """A half-made chart is not a result: the model fixes the script from its error."""
    keep_in = tmp_path / "kept"
    script = (
        "import os\n"
        "open(os.path.join(os.environ['OUTPUT_DIR'], 'half.csv'), 'w').write('a\\n')\n"
        "print('loaded')\n"
        "raise KeyError('revenu')\n"
    )

    run = run_analysis_script(script, [_sales(tmp_path)], keep_in)

    assert not run.ok
    assert run.error == "KeyError: 'revenu'"
    assert run.traceback_tail is not None and 'script.py", line 4' in run.traceback_tail
    assert run.stdout == "loaded\n"
    assert run.kept == ()
    assert not keep_in.exists()


def test_a_flood_on_stdout_keeps_its_start_and_counts_the_rest(
    tmp_path: Path,
) -> None:
    """A script that prints a whole frame must not fill the worker's memory."""
    script = "import sys\nsys.stdout.write('a' * 10_000_000)\n"

    run = run_analysis_script(script, [_sales(tmp_path)], tmp_path / "kept")

    assert run.ok
    assert len(run.stdout) == 64 * 1024
    assert run.stdout_cut == 10_000_000 - 64 * 1024


def test_folders_and_files_past_the_limits_are_named_but_not_kept(
    tmp_path: Path,
) -> None:
    """Only files at OUTPUT_DIR's top are kept, at most twenty of them."""
    keep_in = tmp_path / "kept"
    script = (
        "import os\n"
        "out = os.environ['OUTPUT_DIR']\n"
        "os.mkdir(os.path.join(out, 'nested'))\n"
        "for n in range(22):\n"
        "    open(os.path.join(out, f'table-{n:02}.csv'), 'w').write('a\\n1\\n')\n"
    )

    run = run_analysis_script(script, [_sales(tmp_path)], keep_in)

    assert run.ok
    assert run.kept == tuple(f"table-{n:02}.csv" for n in range(20))
    assert run.left_out == ("nested", "table-20.csv", "table-21.csv")
    assert sorted(os.listdir(keep_in)) == list(run.kept)


def test_two_inputs_of_one_name_both_arrive(tmp_path: Path) -> None:
    """Two sources may share a file name; the second gets its id."""
    first = _sales(tmp_path)
    other = tmp_path / "documents" / "9" / "Sales 2026.csv"
    other.parent.mkdir(parents=True)
    other.write_text("month,revenue\nMar,1\n", encoding="utf-8")
    second = AnalysisInput(path=other, name="Sales 2026.csv", document_id=9, title="Q1")
    script = (
        "import os, json\n"
        "listed = json.load(open(os.path.join(os.environ['INPUT_DIR'], 'manifest.json')))\n"
        "print([entry['file'] for entry in listed])\n"
    )

    run = run_analysis_script(script, [first, second], tmp_path / "kept")

    assert run.ok, run.traceback_tail
    assert run.stdout == "['Sales 2026.csv', 'Sales 2026 [9].csv']\n"


def test_the_child_gets_the_analysis_contract_and_no_document_paths(
    tmp_path: Path, data_dir: Path
) -> None:
    """INPUT_DIR and OUTPUT_DIR in the run folder, charts drawn without a display."""
    script = (
        "import json, os\n"
        "print(json.dumps({k: os.environ.get(k) for k in "
        "('INPUT_DIR', 'OUTPUT_DIR', 'MPLBACKEND', 'OUTPUT_PATH', 'IMAGES_DIR')}))\n"
    )

    run = run_analysis_script(script, [_sales(tmp_path)], tmp_path / "kept")

    assert run.ok, run.traceback_tail
    seen = json.loads(run.stdout)
    folder = Path(seen["INPUT_DIR"]).parent
    assert folder.parent == _scripts_root(data_dir)
    assert seen["OUTPUT_DIR"] == str(folder / "output")
    assert seen["MPLBACKEND"] == "Agg"
    assert seen["OUTPUT_PATH"] is None and seen["IMAGES_DIR"] is None


def test_only_tables_charts_and_data_files_are_kept(tmp_path: Path) -> None:
    """A Markdown file named like AGENTS.md in a thread's outputs would read as instructions."""
    keep_in = tmp_path / "kept"
    script = (
        "import os\n"
        "out = os.environ['OUTPUT_DIR']\n"
        "for name in ('AGENTS.md', 'run.py', 'notes.txt', 'Totals.XLSX'):\n"
        "    open(os.path.join(out, name), 'w').write('x')\n"
    )

    run = run_analysis_script(script, [_sales(tmp_path)], keep_in)

    assert run.ok, run.traceback_tail
    assert run.kept == ("Totals.xlsx", "notes.txt")
    assert run.left_out == ("AGENTS.md", "run.py")
