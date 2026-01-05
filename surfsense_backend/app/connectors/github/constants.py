"""Constants for GitHub connector with gitingest."""

SKIPPED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "build",
    "dist",
    "target",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".vscode",
    ".idea",
    ".project",
    ".settings",
    "tmp",
    "logs",
}

CODE_EXTENSIONS = set()
DOC_EXTENSIONS = set()
MAX_FILE_SIZE = 10 * 1024 * 1024

