"""Prefixed UUID generators for stream parts."""

from __future__ import annotations

import uuid


def generate_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


def generate_text_id() -> str:
    return f"text_{uuid.uuid4().hex}"


def generate_reasoning_id() -> str:
    return f"reasoning_{uuid.uuid4().hex}"


def generate_tool_call_id() -> str:
    return f"call_{uuid.uuid4().hex}"


def generate_subagent_run_id() -> str:
    return f"subagent_{uuid.uuid4().hex}"
