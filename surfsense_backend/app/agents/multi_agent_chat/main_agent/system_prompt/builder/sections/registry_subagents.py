"""Dynamic ``<registry_subagents>`` block: **task** specialists actually built for this workspace."""

from __future__ import annotations


def build_registry_subagents_section(
    registry_subagent_lines: list[tuple[str, str]] | None,
) -> str:
    if registry_subagent_lines is None:
        return ""
    if not registry_subagent_lines:
        return (
            "\n<registry_subagents>\n"
            "No registry specialists are listed for **task** in this workspace.\n"
            "</registry_subagents>\n"
        )
    bullets = "\n".join(
        f"- **{name}** — {desc}" for name, desc in registry_subagent_lines
    )
    return (
        "\n<registry_subagents>\n"
        "These specialists are registered for **task** (routes without a matching connector are omitted).\n"
        f"{bullets}\n"
        "The runtime may also offer a general-purpose **task** helper with your tools in a separate context.\n"
        "Pick the specialist by **name**. Put full instructions in the task prompt; they do not see this thread.\n"
        "</registry_subagents>\n"
    )
