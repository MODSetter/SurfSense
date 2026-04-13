#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for validate-module.py"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-module.py"

CSV_HEADER = "module,skill,display-name,menu-code,description,action,args,phase,after,before,required,output-location,outputs\n"


def create_module(tmp: Path, skills: list[str] | None = None, csv_rows: str = "",
                  yaml_content: str = "", setup_name: str = "tst-setup") -> Path:
    """Create a minimal module structure for testing."""
    module_dir = tmp / "module"
    module_dir.mkdir()

    # Setup skill
    setup = module_dir / setup_name
    setup.mkdir()
    (setup / "SKILL.md").write_text("---\nname: " + setup_name + "\n---\n# Setup\n")
    (setup / "assets").mkdir()
    (setup / "assets" / "module.yaml").write_text(
        yaml_content or 'code: tst\nname: "Test Module"\ndescription: "A test module"\n'
    )
    (setup / "assets" / "module-help.csv").write_text(CSV_HEADER + csv_rows)

    # Other skills
    for skill in (skills or []):
        skill_dir = module_dir / skill
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"---\nname: {skill}\n---\n# {skill}\n")

    return module_dir


def run_validate(module_dir: Path) -> tuple[int, dict]:
    """Run the validation script and return (exit_code, parsed_json)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(module_dir)],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw_stdout": result.stdout, "raw_stderr": result.stderr}
    return result.returncode, data


def test_valid_module():
    """A well-formed module should pass."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        csv_rows = 'Test Module,tst-foo,Do Foo,DF,Does the foo thing,run,,anytime,,,false,output_folder,report\n'
        module_dir = create_module(tmp, skills=["tst-foo"], csv_rows=csv_rows)

        code, data = run_validate(module_dir)
        assert code == 0, f"Expected pass: {data}"
        assert data["status"] == "pass"
        assert data["summary"]["total_findings"] == 0


def test_missing_setup_skill():
    """Module with no setup skill should fail critically."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = tmp / "module"
        module_dir.mkdir()
        skill = module_dir / "tst-foo"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: tst-foo\n---\n")

        code, data = run_validate(module_dir)
        assert code == 1
        assert any(f["category"] == "structure" for f in data["findings"])


def test_missing_csv_entry():
    """Skill without a CSV entry should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = create_module(tmp, skills=["tst-foo", "tst-bar"],
                                   csv_rows='Test Module,tst-foo,Do Foo,DF,Does foo,run,,anytime,,,false,output_folder,report\n')

        code, data = run_validate(module_dir)
        assert code == 1
        missing = [f for f in data["findings"] if f["category"] == "missing-entry"]
        assert len(missing) == 1
        assert "tst-bar" in missing[0]["message"]


def test_orphan_csv_entry():
    """CSV entry for nonexistent skill should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        csv_rows = 'Test Module,tst-ghost,Ghost,GH,Does not exist,run,,anytime,,,false,output_folder,report\n'
        module_dir = create_module(tmp, skills=[], csv_rows=csv_rows)

        code, data = run_validate(module_dir)
        orphans = [f for f in data["findings"] if f["category"] == "orphan-entry"]
        assert len(orphans) == 1
        assert "tst-ghost" in orphans[0]["message"]


def test_duplicate_menu_codes():
    """Duplicate menu codes should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        csv_rows = (
            'Test Module,tst-foo,Do Foo,DF,Does foo,run,,anytime,,,false,output_folder,report\n'
            'Test Module,tst-foo,Also Foo,DF,Also does foo,other,,anytime,,,false,output_folder,report\n'
        )
        module_dir = create_module(tmp, skills=["tst-foo"], csv_rows=csv_rows)

        code, data = run_validate(module_dir)
        dupes = [f for f in data["findings"] if f["category"] == "duplicate-menu-code"]
        assert len(dupes) == 1
        assert "DF" in dupes[0]["message"]


def test_invalid_before_after_ref():
    """Before/after references to nonexistent capabilities should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        csv_rows = 'Test Module,tst-foo,Do Foo,DF,Does foo,run,,anytime,tst-ghost:phantom,,false,output_folder,report\n'
        module_dir = create_module(tmp, skills=["tst-foo"], csv_rows=csv_rows)

        code, data = run_validate(module_dir)
        refs = [f for f in data["findings"] if f["category"] == "invalid-ref"]
        assert len(refs) == 1
        assert "tst-ghost:phantom" in refs[0]["message"]


def test_missing_yaml_fields():
    """module.yaml with missing required fields should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        csv_rows = 'Test Module,tst-foo,Do Foo,DF,Does foo,run,,anytime,,,false,output_folder,report\n'
        module_dir = create_module(tmp, skills=["tst-foo"], csv_rows=csv_rows,
                                   yaml_content='code: tst\n')

        code, data = run_validate(module_dir)
        yaml_findings = [f for f in data["findings"] if f["category"] == "yaml"]
        assert len(yaml_findings) >= 1  # at least name or description missing


def test_empty_csv():
    """CSV with header but no rows should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = create_module(tmp, skills=["tst-foo"], csv_rows="")

        code, data = run_validate(module_dir)
        assert code == 1
        empty = [f for f in data["findings"] if f["category"] == "csv-empty"]
        assert len(empty) == 1


def create_standalone_module(tmp: Path, skill_name: str = "my-skill",
                             csv_rows: str = "", yaml_content: str = "",
                             include_setup_md: bool = True,
                             include_merge_scripts: bool = True) -> Path:
    """Create a minimal standalone module structure for testing."""
    module_dir = tmp / "module"
    module_dir.mkdir()

    skill = module_dir / skill_name
    skill.mkdir()
    (skill / "SKILL.md").write_text(f"---\nname: {skill_name}\n---\n# {skill_name}\n")

    assets = skill / "assets"
    assets.mkdir()
    (assets / "module.yaml").write_text(
        yaml_content or 'code: tst\nname: "Test Module"\ndescription: "A standalone test module"\n'
    )
    if not csv_rows:
        csv_rows = f'Test Module,{skill_name},Do Thing,DT,Does the thing,run,,anytime,,,false,output_folder,artifact\n'
    (assets / "module-help.csv").write_text(CSV_HEADER + csv_rows)

    if include_setup_md:
        (assets / "module-setup.md").write_text("# Module Setup\nStandalone registration.\n")

    if include_merge_scripts:
        scripts = skill / "scripts"
        scripts.mkdir()
        (scripts / "merge-config.py").write_text("# merge-config\n")
        (scripts / "merge-help-csv.py").write_text("# merge-help-csv\n")

    return module_dir


def test_valid_standalone_module():
    """A well-formed standalone module should pass with standalone=true in info."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = create_standalone_module(tmp)

        code, data = run_validate(module_dir)
        assert code == 0, f"Expected pass: {data}"
        assert data["status"] == "pass"
        assert data["info"].get("standalone") is True
        assert data["summary"]["total_findings"] == 0


def test_standalone_missing_module_setup_md():
    """Standalone module without assets/module-setup.md should fail."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = create_standalone_module(tmp, include_setup_md=False)

        code, data = run_validate(module_dir)
        assert code == 1
        structure_findings = [f for f in data["findings"] if f["category"] == "structure"]
        assert any("module-setup.md" in f["message"] for f in structure_findings)


def test_standalone_missing_merge_scripts():
    """Standalone module without merge scripts should fail."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = create_standalone_module(tmp, include_merge_scripts=False)

        code, data = run_validate(module_dir)
        assert code == 1
        structure_findings = [f for f in data["findings"] if f["category"] == "structure"]
        assert any("merge-config.py" in f["message"] for f in structure_findings)


def test_standalone_csv_validation():
    """Standalone module CSV should be validated the same as multi-skill."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Duplicate menu codes
        csv_rows = (
            'Test Module,my-skill,Do Thing,DT,Does thing,run,,anytime,,,false,output_folder,artifact\n'
            'Test Module,my-skill,Also Thing,DT,Also does thing,other,,anytime,,,false,output_folder,report\n'
        )
        module_dir = create_standalone_module(tmp, csv_rows=csv_rows)

        code, data = run_validate(module_dir)
        dupes = [f for f in data["findings"] if f["category"] == "duplicate-menu-code"]
        assert len(dupes) == 1
        assert "DT" in dupes[0]["message"]


def test_multi_skill_not_detected_as_standalone():
    """A folder with two skills and no setup skill should fail (not detected as standalone)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module_dir = tmp / "module"
        module_dir.mkdir()

        for name in ("skill-a", "skill-b"):
            skill = module_dir / name
            skill.mkdir()
            (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
            (skill / "assets").mkdir()
            (skill / "assets" / "module.yaml").write_text(f'code: tst\nname: "Test"\ndescription: "Test"\n')

        code, data = run_validate(module_dir)
        assert code == 1
        # Should fail because it's neither a setup-skill module nor a single-skill standalone
        assert any("No setup skill found" in f["message"] for f in data["findings"])


def test_nonexistent_directory():
    """Nonexistent path should return error."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "/nonexistent/path"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    data = json.loads(result.stdout)
    assert data["status"] == "error"


if __name__ == "__main__":
    tests = [
        test_valid_module,
        test_missing_setup_skill,
        test_missing_csv_entry,
        test_orphan_csv_entry,
        test_duplicate_menu_codes,
        test_invalid_before_after_ref,
        test_missing_yaml_fields,
        test_empty_csv,
        test_valid_standalone_module,
        test_standalone_missing_module_setup_md,
        test_standalone_missing_merge_scripts,
        test_standalone_csv_validation,
        test_multi_skill_not_detected_as_standalone,
        test_nonexistent_directory,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
