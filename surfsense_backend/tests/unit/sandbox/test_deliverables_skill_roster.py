import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PROMPT_PATH = (
    REPO_ROOT
    / "surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins"
    / "deliverables/system_prompt.md"
)
SKILLS_ROOT = REPO_ROOT / "docker/sandbox/skills"
FRONTEND_DESIGN_PATH = SKILLS_ROOT / "frontend-design/DESIGN.md"
SANDBOX_DOCKERFILE = REPO_ROOT / "docker/sandbox/Dockerfile"


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
    assert '`verify_artifact(path=path, format="<format>")`' in prompt
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


def test_format_skills_share_explicit_verify_and_save_contract():
    for name in ("pdf", "docx", "pptx", "xlsx", "html"):
        skill = _skill(name)
        assert "`load_artifact_for_revision`" in skill
        assert "`expected_output_path`" in skill
        assert f'`verify_artifact(path=output_path, format="{name}")`' in skill
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
    assert "populate every\n  visible placeholder with final content" in pptx
    assert "Never guess or hardcode a font-file path" in pptx
    assert "`fc-match" in pptx
    assert "delete obsolete elements before\n   adding replacements" in pptx
    assert pptx.index("Run the local checks") < pptx.index(
        '`verify_artifact(path=output_path, format="pptx")`'
    )

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


def test_deliverables_prompt_routes_interactive_requests_to_html_before_pdf_fallback():
    prompt = _prompt()
    html_route = "controls update results → HTML"
    pdf_fallback = "prefer PDF for a finished deliverable"

    assert html_route in prompt
    assert '`load_artifact_instructions(artifact_type="html")`' in prompt
    assert prompt.index(html_route) < prompt.index(pdf_fallback)


def test_deliverables_prompt_routes_mindmaps_before_html_and_pdf_defaults():
    prompt = _prompt()
    mindmap_route = "show a concept\n  hierarchy → mindmap"
    html_route = "controls update results → HTML"
    pdf_fallback = "prefer PDF for a finished deliverable"

    assert mindmap_route in prompt
    assert '`load_artifact_instructions(artifact_type="mindmap")`' in prompt
    assert prompt.index(mindmap_route) < prompt.index(html_route)
    assert prompt.index(mindmap_route) < prompt.index(pdf_fallback)
    assert "flowcharts, process flows, sequence\n  diagrams" in prompt


def test_deliverables_prompt_routes_flashcards_and_skill_uses_universal_save():
    prompt = _prompt()
    flashcards_route = "deck for recall practice → flashcards"
    pdf_fallback = "prefer PDF for a finished deliverable"
    skill = _skill("flashcards")

    assert flashcards_route in prompt
    assert '`load_artifact_instructions(artifact_type="flashcards")`' in prompt
    assert prompt.index(flashcards_route) < prompt.index(pdf_fallback)
    assert 'format="flashcards"' in skill
    assert 'save_artifact(path="/workspace/<slug>.json", title="...")' in skill
    assert "Do not pass `markdown_representation`" in skill
    assert "Infer unspecified\n  count and difficulty instead of asking" in prompt
    assert "Do not ask for confirmation." in skill
    assert "Report insufficient material only after finding fewer than 15" in skill
    assert "separate" not in skill.lower() or "separate Markdown summary" in skill


def test_deliverables_prompt_routes_quizzes_and_skill_uses_universal_save():
    prompt = _prompt()
    skill = _skill("quiz")

    assert "Use quiz for scored multiple-choice tests" in prompt
    assert '`load_artifact_instructions(artifact_type="quiz")`' in prompt
    assert "but not for surveys" in prompt
    assert 'format="quiz"' in skill
    assert 'save_artifact(path="/workspace/<slug>.json", title="...")' in skill
    assert "5–30 questions" in skill
    assert "otherwise create exactly 10" in skill
    assert "exactly four distinct options" in skill


def test_mindmap_skill_binds_markdown_to_the_png_without_custom_styling():
    skill = _skill("mindmap")

    assert "node /opt/remotion/render-mindmap.mjs" in skill
    assert 'path="/workspace/<slug>.png"' in skill
    assert 'format="mindmap"' in skill
    assert 'markdown_path="/workspace/<slug>.md"' in skill
    assert "byte-for-byte the verified source" in skill
    assert "do not author CSS, colors, HTML, SVG, renderer\noptions" in skill
    assert "`markmap-cli`" in skill


def test_infographic_style_change_reopens_picker_without_new_artifact():
    prompt = _prompt()
    skill = _skill("infographic")

    assert '`load_artifact_instructions(artifact_type="infographic"' in prompt
    assert "`change_infographic_style=True` only if they asked" in prompt
    assert "do not list presets" in prompt
    assert "`change_infographic_style=True` only if the user asked" in skill
    assert "Do not list presets." in skill


def test_shared_frontend_design_is_composed_without_becoming_a_format_skill():
    dockerfile = SANDBOX_DOCKERFILE.read_text()

    assert FRONTEND_DESIGN_PATH.is_file()
    assert not FRONTEND_DESIGN_PATH.with_name("SKILL.md").exists()
    assert 'test -f "${skill}/SKILL.md" || continue' in dockerfile
    assert (
        "cat /tmp/surfsense-skills/frontend-design/DESIGN.md >> "
        '"/opt/skills/${name}/SKILL.md"'
    ) in dockerfile
