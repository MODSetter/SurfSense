from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Called with True to force a refresh, after the endpoint refused the token.
AccessToken = Callable[[bool], Awaitable[str]]


@dataclass(frozen=True)
class ApiKey:
    """A connection's own key: the whole Responses request, and a 401 is the key's."""

    key: str | None


@dataclass(frozen=True)
class PlanToken:
    """A ChatGPT plan's token: refreshed once on a 401, under the plan's limits."""

    access_token: AccessToken


Credential = ApiKey | PlanToken
