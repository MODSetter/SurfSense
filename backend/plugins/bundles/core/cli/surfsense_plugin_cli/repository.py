"""Where this repository keeps the plugins and the SDK they run on."""

from pathlib import Path

CORE = Path(__file__).resolve().parents[2]
PLUGINS = CORE.parent
SDK = CORE / "sdk"
