"""Module entry point: ``python -m surfsense_evals ...``.

Delegates to ``core.cli.main``. ``core.cli`` lazily imports
``surfsense_evals.suites`` so every benchmark gets a chance to register
before argparse builds its subcommand groups.
"""

from __future__ import annotations

from surfsense_evals.core.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
