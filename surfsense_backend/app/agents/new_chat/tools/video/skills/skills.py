from pathlib import Path

_SKILLS_DIR = Path(__file__).parent

SKILL_NAMES: list[str] = [
    # Guidance skills (patterns and rules)
    "charts",
    "typography",
    "social-media",
    "messaging",
    "3d",
    "transitions",
    "sequencing",
    "spring-physics",
    # Example skills (complete working code references)
    "example-histogram",
    "example-progress-bar",
    "example-text-rotation",
    "example-falling-spheres",
    "example-animated-shapes",
    "example-lottie",
    "example-gold-price-chart",
    "example-typewriter-highlight",
    "example-word-carousel",
]


def load_skill_content(skill: str) -> str:
    path = _SKILLS_DIR / f"{skill}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_combined_skill_content(skills: list[str]) -> str:
    if not skills:
        return ""
    contents = [c for s in skills if (c := load_skill_content(s))]
    return "\n\n---\n\n".join(contents)
