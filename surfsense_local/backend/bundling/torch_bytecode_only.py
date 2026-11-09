"""torch and torchvision ship as bytecode, not as bytecode plus their sources.

The contrib hooks choose 'pyz+py' for TorchScript, which nothing here uses.
torch's config modules read their own source when imported
(torch/utils/_config_module.py), so they alone keep it, or `import torch` fails.
"""

from pathlib import Path

from PyInstaller.utils.hooks import get_package_paths


def _config_modules() -> list[str]:
    """Modules that call install_config_module, found in the installed torch."""
    _, package = get_package_paths("torch")
    root = Path(package)
    found = []
    for source in root.rglob("*.py"):
        if "install_config_module(" not in source.read_text(
            encoding="utf-8", errors="ignore"
        ):
            continue
        parts = source.relative_to(root.parent).with_suffix("").parts
        found.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return found


def collection_modes() -> dict[str, str]:
    """Analysis(module_collection_mode=...) for torch and torchvision."""
    modes = {"torch": "pyz", "torchvision": "pyz"}
    modes.update(dict.fromkeys(_config_modules(), "pyz+py"))
    return modes
