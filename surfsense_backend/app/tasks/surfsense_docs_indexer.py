"""
Surfsense documentation indexer.
Indexes MDX documentation files at migration time.
"""

import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to docs relative to project root
DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "surfsense_web" / "content" / "docs"


def parse_mdx_frontmatter(content: str) -> tuple[str, str]:
    """
    Parse MDX file to extract frontmatter title and content.

    Args:
        content: Raw MDX file content

    Returns:
        Tuple of (title, content_without_frontmatter)
    """
    # Match frontmatter between --- markers
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if match:
        frontmatter = match.group(1)
        content_without_frontmatter = content[match.end():]

        # Extract title from frontmatter
        title_match = re.search(r"^title:\s*(.+)$", frontmatter, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        # Remove quotes if present
        title = title.strip("\"'")

        return title, content_without_frontmatter.strip()

    return "Untitled", content.strip()


def get_all_mdx_files() -> list[Path]:
    """
    Get all MDX files from the docs directory.

    Returns:
        List of Path objects for each MDX file
    """
    if not DOCS_DIR.exists():
        logger.warning(f"Docs directory not found: {DOCS_DIR}")
        return []

    return list(DOCS_DIR.rglob("*.mdx"))


def generate_surfsense_docs_content_hash(content: str) -> str:
    """Generate SHA-256 hash for Surfsense docs content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

