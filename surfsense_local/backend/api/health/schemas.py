from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Payload of the liveness probe."""

    status: Literal["ok"]
