"""Apply ``edit`` permission decisions to tool calls.

Edited-arg extraction now lives in :mod:`hitl_wire.decision` (single parser
for all approval paths); this module owns the merge step that produces a
fresh tool-call dict for the orchestrator.
"""

from .merge import merge_edited_args

__all__ = ["merge_edited_args"]
