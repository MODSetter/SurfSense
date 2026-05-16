from __future__ import annotations

FILESYSTEM_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "glob",
        "grep",
        "ls",
        "mkdir",
        "move_file",
        "rm",
        "rmdir",
        "write_todos",
        "write_file",
        "edit_file",
        "execute",
    }
)
