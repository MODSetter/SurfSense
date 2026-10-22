"""Bytecode without docstrings, except where something reads them.

Built at optimize=2, which drops docstrings and asserts from the library
bytecode. The packages below go back to level 0: transformers builds model
classes from their docstrings (auto_docstring raises without them), the app's
own docstrings are the API's /docs and its asserts are checks, Docling's asserts
steer its pipelines, and pydantic, FastAPI, Starlette and MCP turn docstrings
into schema descriptions. The interpreter itself stays at level 0, so a
model-written script keeps its asserts.
"""

KEEP_DOCSTRINGS = (
    "transformers",
    "api",
    "modules",
    "shared",
    "worker",
    "frozen_entry",
    "main",
    "docling",
    "docling_core",
    "docling_ibm_models",
    "docling_parse",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "fastapi",
    "starlette",
    "mcp",
    "claude_agent_sdk",
)


def with_kept_docstrings(pure: list) -> list:
    """The pure TOC, with the packages above compiled at level 0."""
    return [
        (
            name,
            source,
            "PYMODULE" if name.split(".")[0] in KEEP_DOCSTRINGS else typecode,
        )
        for name, source, typecode in pure
    ]
