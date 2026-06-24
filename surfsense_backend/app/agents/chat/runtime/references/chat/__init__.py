"""Resolve ``@chat`` mentions into pointers, access-checked, titles only."""

from __future__ import annotations

from .resolver import resolve_chat_references

__all__ = ["resolve_chat_references"]
