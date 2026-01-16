"""
Utility functions for chat comments, including mention parsing.
"""

import re
from uuid import UUID

# Pattern to match @[uuid] mentions in comment content
MENTION_PATTERN = re.compile(r"@\[([0-9a-fA-F-]{36})\]")


def parse_mentions(content: str) -> list[UUID]:
    """
    Extract user UUIDs from @[uuid] mentions in content.

    Args:
        content: Comment text that may contain @[uuid] mentions

    Returns:
        List of unique user UUIDs found in the content
    """
    matches = MENTION_PATTERN.findall(content)
    unique_uuids = []
    seen = set()

    for match in matches:
        try:
            uuid = UUID(match)
            if uuid not in seen:
                seen.add(uuid)
                unique_uuids.append(uuid)
        except ValueError:
            # Invalid UUID format, skip
            continue

    return unique_uuids


def render_mentions(content: str, user_names: dict[UUID, str]) -> str:
    """
    Replace @[uuid] mentions with @{DisplayName} in content.

    Uses curly braces as delimiters for unambiguous frontend parsing.

    Args:
        content: Comment text with @[uuid] mentions
        user_names: Dict mapping user UUIDs to display names

    Returns:
        Content with mentions rendered as @{DisplayName}
    """

    def replace_mention(match: re.Match) -> str:
        try:
            uuid = UUID(match.group(1))
            name = user_names.get(uuid)
            if name:
                return f"@{{{name}}}"
            # Keep original format if user not found
            return match.group(0)
        except ValueError:
            return match.group(0)

    return MENTION_PATTERN.sub(replace_mention, content)
