"""The router is the only switch: every catalog key has exactly one pipeline."""

import inspect

import pytest

from modules.artifacts.formats import FORMATS
from worker.studio import job_router

pytestmark = pytest.mark.unit


def test_the_router_names_every_catalog_format_and_nothing_else() -> None:
    """The API offers exactly the formats the worker can route, key for key."""
    assert {kind.value for kind in job_router.Kind} == {fmt.key for fmt in FORMATS}


def test_every_kind_has_a_pipeline() -> None:
    """A kind without a `case` would surface as None at job time; catch it here."""
    for kind in job_router.Kind:
        assert callable(job_router.pipeline_for(kind)), kind


def test_every_pipeline_takes_the_models_its_format_declares() -> None:
    """The harness passes requires_roles positionally, then sources and prompt."""
    for fmt in FORMATS:
        render = job_router.pipeline_for(job_router.Kind(fmt.key))
        expected = len(fmt.requires_roles) + 2
        assert len(inspect.signature(render).parameters) == expected, fmt.key
