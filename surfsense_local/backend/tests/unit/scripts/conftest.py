"""Put the authoring helpers on the path the way running the script does.

`uv run scripts/refresh_curated_models.py` puts `scripts/` on `sys.path`, which
is why that file imports `curated.x` rather than `scripts.curated.x`. Importing
these modules any other way here would test them under a name they are never
loaded with.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
