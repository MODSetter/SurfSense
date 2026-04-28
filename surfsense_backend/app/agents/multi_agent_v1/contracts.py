"""Contracts for multi_agent_v1 orchestrator and subagent communication."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkerBudget(BaseModel):
    max_steps: int = Field(default=1, ge=1)
    max_duration_ms: int = Field(default=15_000, ge=100)


class SubagentTaskPlan(BaseModel):
    domain: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)
    budget: WorkerBudget = Field(default_factory=WorkerBudget)


class GroundingEvidence(BaseModel):
    claim: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    snippet: str = ""


class SubagentResult(BaseModel):
    status: Literal["success", "partial", "error"]
    summary: str = ""
    evidence: list[GroundingEvidence] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    needs_human: bool = False
    error_class: str | None = None
