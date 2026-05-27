"""``ManualTriggerParams`` — params for the ``manual`` trigger (empty in v1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ManualTriggerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
