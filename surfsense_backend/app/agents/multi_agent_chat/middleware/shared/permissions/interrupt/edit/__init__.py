"""Apply ``edit`` permission decisions to tool calls (extract + merge)."""

from .extract import extract_edited_args
from .merge import merge_edited_args

__all__ = ["extract_edited_args", "merge_edited_args"]
