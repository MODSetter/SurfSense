"""Names that must be unique within their list, so the app can find each one.

Read from the raw manifest.json rather than the validated manifest, so a duplicate is
reported in the same pass as every other error.
"""


def errors_for_duplicate_names(declared: dict) -> list[str]:
    entries = _items(declared, "entries")
    errors = _repeated("entries", "entry", entries)
    errors += _repeated("secrets", "secret", _items(declared, "secrets"))
    for index, entry in enumerate(entries):
        errors += _repeated(
            f"entries[{index}].inputs", "input", _items(entry, "inputs")
        )
    return errors


def _items(parent: object, field: str) -> list[dict]:
    items = parent.get(field) if isinstance(parent, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _repeated(where: str, kind: str, items: list[dict]) -> list[str]:
    errors, seen = [], set()
    for index, item in enumerate(items):
        name = item.get("name")
        if not isinstance(name, str):
            continue
        if name in seen:
            errors.append(f"{where}[{index}].name: another {kind} is named {name}")
        seen.add(name)
    return errors
