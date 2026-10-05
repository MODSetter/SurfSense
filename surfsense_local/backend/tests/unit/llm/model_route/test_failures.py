"""A generation's failure crosses the route and comes out as the same type."""

import httpx
import pytest

from modules.egress.service import EgressDeniedError
from modules.llm.model_route.failures import as_frame, raise_from_frame
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.providers.stream_deadline import StreamTimeoutError
from modules.llm.resolution import ModelResolutionError

pytestmark = pytest.mark.unit


def _crossed(failure: Exception) -> Exception:
    with pytest.raises(Exception) as raised:
        raise_from_frame(as_frame(failure))
    return raised.value


def test_a_provider_status_keeps_its_status() -> None:
    """The chat and Studio sort failures by status, so it must survive the trip."""
    request = httpx.Request("POST", "http://model")
    refused = httpx.HTTPStatusError(
        "slow down", request=request, response=httpx.Response(429, request=request)
    )

    crossed = _crossed(refused)

    assert isinstance(crossed, httpx.HTTPStatusError)
    assert crossed.response.status_code == 429


def test_a_subscription_that_has_to_sign_in_again_says_so() -> None:
    """Studio shows the same sign-in message it shows today."""
    crossed = _crossed(SignInRequiredError())

    assert isinstance(crossed, SignInRequiredError)
    assert str(crossed) == str(SignInRequiredError())


def test_a_used_up_plan_says_so() -> None:
    """A used-up plan keeps its own type, which nothing retries."""
    crossed = _crossed(PlanLimitError("the plan's limit is reached until 4 pm"))

    assert isinstance(crossed, PlanLimitError)
    assert str(crossed) == "the plan's limit is reached until 4 pm"


def test_a_refused_host_names_the_host() -> None:
    """The refusal names the host the person has to allow."""
    crossed = _crossed(EgressDeniedError("host:api.example.com"))

    assert isinstance(crossed, EgressDeniedError)
    assert crossed.host == "api.example.com"


def test_a_model_that_never_started_keeps_which_budget_ran_out() -> None:
    """A model that never started reads differently from one that stalled."""
    crossed = _crossed(StreamTimeoutError(300.0, first_item=True, subject="the model"))

    assert isinstance(crossed, StreamTimeoutError)
    assert (crossed.seconds, crossed.first_item) == (300.0, True)


def test_a_model_gone_since_is_a_resolution_error() -> None:
    """A model removed mid-job fails as one that cannot be resolved."""
    crossed = _crossed(ModelResolutionError("the local model is no longer installed"))

    assert isinstance(crossed, ModelResolutionError)


def test_an_unreachable_runtime_is_a_network_error() -> None:
    """Studio words an unreachable model as it always has."""
    crossed = _crossed(httpx.ConnectError("connection refused"))

    assert isinstance(crossed, httpx.HTTPError)
