"""Lock the ``DispatchError`` exception contract.

``DispatchError`` is the uniform exception type the dispatch layer raises
for any "cannot turn this fire request into a run" condition. Other
modules (templates of error envelopes, run records) compare on
``isinstance(exc, DispatchError)``, so the inheritance is the contract.
"""

from __future__ import annotations

import pytest

from app.automations.dispatch.errors import DispatchError

pytestmark = pytest.mark.unit


def test_dispatch_error_is_exception_subclass_and_carries_message() -> None:
    """Lifting a string into ``DispatchError`` preserves the message and
    behaves as a regular ``Exception`` for ``isinstance`` / ``raise`` /
    ``except`` consumers."""
    error = DispatchError("missing trigger")

    assert isinstance(error, Exception)
    assert str(error) == "missing trigger"

    with pytest.raises(DispatchError):
        raise error
