"""The files a new plugin starts with: one action that adds a note, ready to run."""

import json


def template(plugin_id: str, author: str) -> dict[str, str]:
    """Each file's path in the plugin's folder, and its text."""
    package = plugin_id.replace("-", "_")
    name = plugin_id.replace("-", " ").capitalize()
    manifest = {
        "id": plugin_id,
        "name": name,
        "description": f"What {name} adds to SurfSense, in one line.",
        "author": author,
        "access": "free",
        "hosts": [],
        "actions": [
            {
                "name": "add-note",
                "title": "Add a note",
                "inputs": [
                    {
                        "name": "text",
                        "title": "Text",
                        "kind": "string",
                        "required": True,
                    }
                ],
            }
        ],
    }
    return {
        "manifest.json": json.dumps(manifest, indent=2) + "\n",
        "main.py": (
            f'"""Where SurfSense starts {name}.\n\n'
            'Importing a module registers the actions it marks with @action.\n"""\n\n'
            f"import {package}.add_note  # noqa: F401\n"
        ),
        f"{package}/__init__.py": (
            f'"""{name}\'s own code, in a package named after it, so no module of'
            ' yours can clash with a library."""\n'
        ),
        f"{package}/add_note.py": (
            '"""The add-note action: what the user typed, kept as a note."""\n\n'
            "from surfsense_plugin_sdk import action, document\n\n\n"
            '@action("add-note")\n'
            "def add_note(text: str) -> None:\n"
            '    """Adds the text as a note in the workspace the user ran this in."""\n'
            '    document.add(title="Note", content=text)\n'
        ),
    }
