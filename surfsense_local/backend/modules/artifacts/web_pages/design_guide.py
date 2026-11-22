"""The design guide every model-written page follows, read by the agent's skill and Studio's prompt alike."""

from importlib.resources import files


def design_guide() -> str:
    """The guide in the agent's skill folder, so both paths make the same kind of page."""
    guide = files("modules.agent").joinpath("skills", "surfsense-html", "design.md")
    return guide.read_text(encoding="utf-8").strip()
