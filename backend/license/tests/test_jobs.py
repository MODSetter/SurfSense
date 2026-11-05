"""A license's jobs, read from ``metadata.jobs`` exactly as the app reads its file."""

from __future__ import annotations

import pytest

from license.jobs import jobs_of

pytestmark = pytest.mark.unit


def test_codes_are_trimmed_and_empty_and_repeated_ones_dropped() -> None:
    assert jobs_of({"jobs": " JOB_A, ,JOB_B,JOB_A "}) == ("JOB_A", "JOB_B")


def test_anything_but_a_string_lists_no_job() -> None:
    assert jobs_of({"jobs": ["JOB_A"]}) == ()
    assert jobs_of({"jobs": None}) == ()


def test_a_license_without_jobs_lists_none() -> None:
    assert jobs_of({}) == ()
