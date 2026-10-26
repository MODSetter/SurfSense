import pytest
from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    RateLimitInfo,
    ResultMessage,
    SystemMessage,
    TextBlock,
)

from modules.egress.service import EgressDeniedError
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.subscriptions.claude.errors import (
    ClaudePlanLimitError,
    ClaudeRunError,
    ClaudeSignInRequiredError,
    failure_of,
)

pytestmark = pytest.mark.unit


def _assistant(error: str | None = None) -> AssistantMessage:
    return AssistantMessage(
        content=[TextBlock("hi")], model="claude-haiku-5-5", error=error
    )


def _limit(status: str) -> RateLimitEvent:
    info = RateLimitInfo(
        status=status, resets_at=1792107600, rate_limit_type="five_hour"
    )
    return RateLimitEvent(rate_limit_info=info, uuid="u", session_id="s")


def _result(*, is_error: bool, errors: list[str] | None = None) -> ResultMessage:
    return ResultMessage(
        subtype="error_during_execution" if is_error else "success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="s",
        errors=errors,
    )


def _api_retry() -> SystemMessage:
    return SystemMessage(subtype="api_retry", data={"attempt": 1, "max_retries": 10})


def test_a_signed_out_claude_code_asks_to_sign_in() -> None:
    """Measured: an empty login fails the first request with authentication_failed."""
    assert isinstance(
        failure_of(_assistant("authentication_failed")), SignInRequiredError
    )
    assert isinstance(
        failure_of(_assistant("authentication_failed")), ClaudeSignInRequiredError
    )


@pytest.mark.parametrize(
    "message",
    [_limit("rejected"), _assistant("rate_limit")],
    ids=["event", "assistant"],
)
def test_a_used_up_plan_is_the_plan_limit(message: object) -> None:
    """Claude Code reports a used-up plan as an event or on the reply itself."""
    assert isinstance(failure_of(message), PlanLimitError)
    assert isinstance(failure_of(message), ClaudePlanLimitError)


@pytest.mark.parametrize(
    "extra",
    [{"isUsingOverage": True}, {"overageInUse": True}],
    ids=["using-overage", "overage-in-use"],
)
def test_a_used_up_plan_on_extra_usage_is_no_failure(extra: dict) -> None:
    """As Claude Code 2.1.301 decides: past the plan's limit, extra usage lets the reply go on."""
    info = RateLimitInfo(
        status="rejected",
        resets_at=1792107600,
        rate_limit_type="five_hour",
        overage_status="allowed",
        raw={"status": "rejected", "overageStatus": "allowed", **extra},
    )
    event = RateLimitEvent(rate_limit_info=info, uuid="u", session_id="s")

    assert failure_of(event) is None


@pytest.mark.parametrize("status", ["allowed", "allowed_warning"])
def test_a_plan_with_room_left_is_no_failure(status: str) -> None:
    """A warning that the plan is nearly used up still answers."""
    assert failure_of(_limit(status)) is None


def test_a_retry_after_the_proxy_refused_is_the_egress_refusal() -> None:
    """Claude Code retries a refused tunnel ten times rather than failing."""
    refusal = EgressDeniedError("host:platform.claude.com")

    assert failure_of(_api_retry(), proxy_refusal=refusal) is refusal


def test_a_retry_the_proxy_did_not_cause_is_no_failure() -> None:
    """An ordinary retry is Claude Code's own business."""
    assert failure_of(_api_retry(), proxy_refusal=None) is None


def test_any_other_failed_run_is_a_run_error() -> None:
    """A failure that is not the plan's or the sign-in's keeps Claude Code's detail."""
    failure = failure_of(_result(is_error=True, errors=["boom"]))

    assert isinstance(failure, ClaudeRunError)
    assert "boom" in str(failure)


@pytest.mark.parametrize(
    "message", [_assistant(), _result(is_error=False)], ids=["text", "success"]
)
def test_an_ordinary_message_is_no_failure(message: object) -> None:
    """Text and a successful result mean nothing went wrong."""
    assert failure_of(message) is None
