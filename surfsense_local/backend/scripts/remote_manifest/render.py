"""The manifest as text: one model per line, so a refresh diff names what changed."""

import json
from typing import Any

__all__ = ["render"]


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render(manifest: dict[str, Any]) -> str:
    lines = ["{"]
    for key, value in manifest.items():
        if key != "providers":
            lines.append(f" {_dump(key)}: {_dump(value)},")
    lines.append(' "providers": {')
    providers = list(manifest["providers"].items())
    for index, (provider_id, provider) in enumerate(providers):
        lines.append(f"  {_dump(provider_id)}: {{")
        for key, value in provider.items():
            if key != "models":
                lines.append(f"   {_dump(key)}: {_dump(value)},")
        lines.append('   "models": {')
        models = list(provider["models"].items())
        for position, (model_id, model) in enumerate(models):
            comma = "," if position < len(models) - 1 else ""
            lines.append(f"    {_dump(model_id)}: {_dump(model)}{comma}")
        lines.append("   }")
        lines.append("  }" + ("," if index < len(providers) - 1 else ""))
    lines.extend([" }", "}"])
    return "\n".join(lines) + "\n"
