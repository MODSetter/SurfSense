"""Constants for GitHub connector."""

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".rs",
    ".m",
    ".sh",
    ".bash",
    ".ps1",
    ".lua",
    ".pl",
    ".pm",
    ".r",
    ".dart",
    ".sql",
}

DOC_EXTENSIONS = {
    ".md",
    ".txt",
    ".rst",
    ".adoc",
    ".html",
    ".htm",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

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

MAX_FILE_SIZE = 1 * 1024 * 1024

