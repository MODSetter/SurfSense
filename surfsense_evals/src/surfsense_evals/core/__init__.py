"""Domain-agnostic infrastructure shared by every suite.

Nothing under ``core/`` knows or cares about a specific evaluation domain.
Suites live under ``surfsense_evals.suites.<domain>.<benchmark>`` and
register themselves with ``core.registry`` on import.
"""

from __future__ import annotations
