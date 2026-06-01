"""SandboxedEnvironment construction with the audited filter/test allowlist."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .allowlist import ALLOWED_FILTERS, ALLOWED_TESTS
from .filters import filter_date, filter_slugify


def _finalize(value: Any) -> Any:
    """Stringify common non-string values at output sites."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _build_env() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        autoescape=False,
        undefined=StrictUndefined,
        finalize=_finalize,
    )
    env.globals.clear()
    env.filters = {k: v for k, v in env.filters.items() if k in ALLOWED_FILTERS}
    env.filters["date"] = filter_date
    env.filters["slugify"] = filter_slugify
    env.tests = {k: v for k, v in env.tests.items() if k in ALLOWED_TESTS}
    return env


ENV: SandboxedEnvironment = _build_env()
