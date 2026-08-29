import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PROMPT_PATH = (
    REPO_ROOT
    / "surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins"
    / "deliverables/system_prompt.md"
)
SKILLS_ROOT = REPO_ROOT / "docker/sandbox/skills"


def _prompt() -> str:
    return PROMPT_PATH.read_text()


def _skill(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text()


def test_deliverables_prompt_lists_every_installed_format_skill():
    advertised = set(re.findall(r"Available format skill: `([^`]+)`", _prompt()))

    installed = set()
    for skill_path in SKILLS_ROOT.glob("*/SKILL.md"):
        match = re.match(
            r"^---\s*\n.*?^name:\s*(\S+)\s*$.*?^---\s*$",
            skill_path.read_text(),
            re.MULTILINE | re.DOTALL,
        )
        assert match is not None, f"{skill_path}: missing name frontmatter"
        installed.add(match.group(1))

    # Video is transitional and advertised only by the flag-aware prompt block.
    assert advertised == installed - {"video"}


def test_deliverables_prompt_uses_pathless_publication_contract():
    prompt = _prompt()

    assert "generate the requested file at a chosen path" in prompt
    assert "`verify_artifact(path=path)`" in prompt
    assert (
        '`save_artifact(path=path, title="...", markdown_representation="...")`'
        in prompt
    )
    assert "regenerate at most once" in prompt
    assert "Markdown is edited and saved directly" in prompt
    assert "distinct artifacts in parallel" in prompt
    assert "distinct output path" in prompt

    assert "`load_artifact_source`" not in prompt
    assert "source_path=" not in prompt
    assert "preview_path=" not in prompt


def test_deliverables_prompt_carries_revision_handles_without_vision_rebuild():
    prompt = _prompt()

    assert "`load_artifact_for_revision(artifact_id=...)`" in prompt
    for field in (
        "`primary_path`",
        "`markdown_path`",
        "`expected_output_path`",
        "`artifact_id`",
        "`expected_generation`",
    ):
        assert field in prompt
    assert "Do not use vision to reconstruct" in prompt
    assert "`verify_artifact` may use vision" in prompt


def test_format_skills_share_pathless_verify_and_save_contract():
    for name in ("pdf", "docx", "pptx", "xlsx"):
        skill = _skill(name)
        assert "`load_artifact_for_revision`" in skill
        assert "`expected_output_path`" in skill
        assert "`verify_artifact(path=output_path)`" in skill
        assert "`save_artifact(path=output_path, title=" in skill
        assert "matching filename stem" in skill
        assert "source_path=" not in skill
        assert "preview_path=" not in skill


def test_format_skills_define_safe_revision_strategy():
    pdf = _skill("pdf")
    assert "`markdown_path`" in pdf
    assert "regenerate the PDF" in pdf
    assert "Do not use vision to reconstruct" in pdf
    assert "Do not embed page numbers" in pdf

    pptx = _skill("pptx")
    assert "Open\n`primary_path` with `python-pptx`" in pptx
    assert "edit that current deck directly" in pptx

    xlsx = _skill("xlsx")
    assert "Open\n`primary_path` with `openpyxl`" in xlsx
    assert "headless LibreOffice" in xlsx
    assert "contains formulas" in xlsx
    assert "recalculated file exists" in xlsx

    docx = _skill("docx")
    assert "`python-docx` to open `primary_path`" in docx
    assert "stop and report the blocker" in docx
    assert "Do not\nsilently rebuild from `markdown_path`" in docx
    assert "explicitly requested or accepted" in docx
    assert "do not fall back to a Markdown-only" in docx
