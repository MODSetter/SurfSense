"""Resolve ``@document`` references.

Two concerns, one subject: ``resolver`` turns document ids into pointer
references for the model, ``referenced`` turns ``@document`` / ``@folder``
mentions into the document ids a retrieval is confined to.
"""

from __future__ import annotations

from .referenced import referenced_document_ids
from .resolver import resolve_document_references

__all__ = ["referenced_document_ids", "resolve_document_references"]
