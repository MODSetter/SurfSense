"""SurfSense Evals — domain-agnostic eval harness.

Public entry-point is the ``surfsense_evals`` CLI (``python -m surfsense_evals``).
Programmatic embedding is a non-goal for now; everything goes through the CLI
+ filesystem outputs (state.json, raw run JSONL, summary.md/json reports).
"""

from __future__ import annotations

__version__ = "0.1.0"
