"""
Utility functions for webcrawler connector.
"""


def parse_webcrawler_urls(initial_urls: str | list | None) -> list[str]:
    """
    Parse URLs from webcrawler INITIAL_URLS value.

    Handles both string (newline-separated) and list formats.

    Args:
        initial_urls: The INITIAL_URLS value (string, list, or None)

    Returns:
        List of parsed, stripped, non-empty URLs
    """
    if initial_urls is None:
        return []

    if isinstance(initial_urls, str):
        return [url.strip() for url in initial_urls.split("\n") if url.strip()]
    elif isinstance(initial_urls, list):
        return [
            url.strip() for url in initial_urls if isinstance(url, str) and url.strip()
        ]
    else:
        return []
