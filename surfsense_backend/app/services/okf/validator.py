"""Minimal OKF v0.1 conformance checks.

A bundle conforms if every non-reserved ``.md`` file has a parseable YAML
frontmatter block whose ``type`` is a non-empty string. Reserved files
(``index.md``, ``log.md``) are exempt from the frontmatter requirement.
Consumers must stay permissive, so this is for producers to self-check what they
emit, not to reject foreign bundles.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

import yaml

from app.services.okf.serializer import INDEX_FILENAME, LOG_FILENAME

_DELIMITER = "---"
RESERVED_FILENAMES = frozenset({INDEX_FILENAME, LOG_FILENAME})

# The OKF v0.1 frontmatter contract, shared by serializer and validator. Only
# ``type`` is mandatory; the rest are recommended.
REQUIRED_FRONTMATTER_KEYS: tuple[str, ...] = ("type",)
RECOMMENDED_FRONTMATTER_KEYS: tuple[str, ...] = (
    "title",
    "description",
    "resource",
    "tags",
    "timestamp",
)


def parse_frontmatter(text: str) -> tuple[dict | None, str | None]:
    """Split an OKF concept into ``(frontmatter_dict, error)``.

    Returns ``(dict, None)`` on success or ``(None, reason)`` if the frontmatter
    block is missing or not a parseable YAML mapping.
    """
    if not text.startswith(_DELIMITER + "\n"):
        return None, "missing opening '---' frontmatter delimiter"
    rest = text[len(_DELIMITER) + 1 :]
    end = rest.find("\n" + _DELIMITER)
    if end == -1:
        return None, "missing closing '---' frontmatter delimiter"
    block = rest[:end]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return None, f"frontmatter is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a YAML mapping"
    return data, None


def validate_concept(text: str) -> list[str]:
    """Return conformance errors for a single concept document (empty == conforms)."""
    frontmatter, error = parse_frontmatter(text)
    if error:
        return [error]
    errors: list[str] = []
    for key in REQUIRED_FRONTMATTER_KEYS:
        value = frontmatter.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"frontmatter '{key}' is missing or empty")
    return errors


def is_conformant_concept(text: str) -> bool:
    """True if a single concept document conforms to OKF v0.1."""
    return not validate_concept(text)


def validate_bundle(files: dict[str, str]) -> dict[str, list[str]]:
    """Validate a bundle given a mapping of relative path -> file contents.

    Only non-reserved ``.md`` files are checked for concept conformance. Returns
    a mapping of path -> errors for every non-conformant file (an empty mapping
    means the whole bundle conforms).
    """
    problems: dict[str, list[str]] = {}
    for path, contents in files.items():
        if not path.endswith(".md"):
            continue
        filename = path.rsplit("/", 1)[-1]
        if filename in RESERVED_FILENAMES:
            continue
        errors = validate_concept(contents)
        if errors:
            problems[path] = errors
    return problems
