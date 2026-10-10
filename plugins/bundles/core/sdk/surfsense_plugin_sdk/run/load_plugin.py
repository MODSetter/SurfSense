"""Imports a plugin's main.py, which registers its actions as it loads."""

import importlib.util
import site
import sys
from pathlib import Path


def load_plugin(folder: Path) -> None:
    """Makes the plugin's code and dependencies importable, then imports main.py."""
    # Appended, never inserted: neither the plugin's modules nor a pinned
    # dependency may shadow the standard library, for the plugin or the SDK.
    sys.path.append(str(folder))
    # addsitedir rather than a path entry, so a dependency's .pth file runs.
    site.addsitedir(str(folder / "site-packages"))

    main = folder / "main.py"
    if not main.is_file():
        sys.exit(f"main.py is missing from {folder}")
    spec = importlib.util.spec_from_file_location("main", main)
    # Never None for a .py file that exists; the check is for the type checker.
    if spec is None or spec.loader is None:
        sys.exit(f"{main} cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules["main"] = module
    spec.loader.exec_module(module)
