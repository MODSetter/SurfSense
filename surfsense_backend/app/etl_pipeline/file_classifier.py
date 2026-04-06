from enum import Enum
from pathlib import PurePosixPath

from app.utils.file_extensions import DOCUMENT_EXTENSIONS, get_document_extensions_for_service

PLAINTEXT_EXTENSIONS = frozenset(
    {
        ".md", ".markdown", ".txt", ".text",
        ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
        ".css", ".scss", ".less", ".sass",
        ".py", ".pyw", ".pyi", ".pyx",
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        ".java", ".kt", ".kts", ".scala", ".groovy",
        ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
        ".cs", ".fs", ".fsx",
        ".go", ".rs", ".rb", ".php", ".pl", ".pm", ".lua", ".swift",
        ".m", ".mm", ".r", ".jl",
        ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
        ".sql", ".graphql", ".gql",
        ".env", ".gitignore", ".dockerignore", ".editorconfig",
        ".makefile", ".cmake",
        ".log", ".rst", ".tex", ".bib", ".org", ".adoc", ".asciidoc",
        ".vue", ".svelte", ".astro",
        ".tf", ".hcl", ".proto",
    }
)

AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
)

DIRECT_CONVERT_EXTENSIONS = frozenset({".csv", ".tsv", ".html", ".htm", ".xhtml"})


class FileCategory(Enum):
    PLAINTEXT = "plaintext"
    AUDIO = "audio"
    DIRECT_CONVERT = "direct_convert"
    UNSUPPORTED = "unsupported"
    DOCUMENT = "document"


def classify_file(filename: str) -> FileCategory:
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix in PLAINTEXT_EXTENSIONS:
        return FileCategory.PLAINTEXT
    if suffix in AUDIO_EXTENSIONS:
        return FileCategory.AUDIO
    if suffix in DIRECT_CONVERT_EXTENSIONS:
        return FileCategory.DIRECT_CONVERT
    if suffix in DOCUMENT_EXTENSIONS:
        return FileCategory.DOCUMENT
    return FileCategory.UNSUPPORTED


def should_skip_for_service(filename: str, etl_service: str | None) -> bool:
    """Return True if *filename* cannot be processed by *etl_service*.

    Plaintext, audio, and direct-convert files are parser-agnostic and never
    skipped.  Document files are checked against the per-parser extension set.
    """
    category = classify_file(filename)
    if category == FileCategory.UNSUPPORTED:
        return True
    if category == FileCategory.DOCUMENT:
        suffix = PurePosixPath(filename).suffix.lower()
        return suffix not in get_document_extensions_for_service(etl_service)
    return False
