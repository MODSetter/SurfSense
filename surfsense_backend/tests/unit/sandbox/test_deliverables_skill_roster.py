import re
from pathlib import Path

from app.services.okf.validator import parse_frontmatter


def test_deliverables_prompt_lists_every_installed_format_skill():
    repo_root = Path(__file__).resolve().parents[4]
    prompt = (
        repo_root
        / "surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins"
        / "deliverables/system_prompt.md"
    ).read_text()
    advertised = set(re.findall(r"Available format skill: `([^`]+)`", prompt))

    installed = set()
    for skill_path in (repo_root / "docker/sandbox/skills").glob("*/SKILL.md"):
        frontmatter, error = parse_frontmatter(skill_path.read_text())
        assert error is None, f"{skill_path}: {error}"
        assert frontmatter is not None
        installed.add(frontmatter["name"])

    assert advertised == installed
