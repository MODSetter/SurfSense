"""The system prompt that asks the model to write one format's builder code."""

from __future__ import annotations

from worker.studio.office.spec import Office

_CONTRACT = """Write one standalone Python script that builds a {label} from the \
sources below, using their facts only.

Author it with the pre-installed `{library}` package and the standard library.
Design the layout however best fits the content — you are not filling a template.

{skill}

The script MUST, at module level:
- assign the finished file's bytes to `output_bytes`;
- assign a short `title` string;
- assign a `summary` string: a faithful Markdown outline of the content, for search.

Build everything in memory: do not read or write files on disk, and do not use
the network. Return only the Python code, with no prose."""


def build(spec: Office, user_prompt: str | None) -> str:
    """The full system prompt for `spec`: the contract, its skill, any emphasis."""
    system = _CONTRACT.format(label=spec.label, library=spec.library, skill=spec.skill)
    if user_prompt:
        system += f"\n\nEmphasise: {user_prompt}."
    return system
