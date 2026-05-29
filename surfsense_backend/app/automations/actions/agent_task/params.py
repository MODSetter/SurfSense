"""``AgentTaskActionParams`` — params for the ``agent_task`` action type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.new_chat import MentionedDocumentInfo


class AgentTaskActionParams(BaseModel):
    """Run a multi_agent_chat turn from an automation step."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        description="User query for the agent; rendered at execute time.",
    )
    auto_approve_all: bool = Field(
        default=False,
        description="If true, every HITL approval is auto-approved; otherwise rejected.",
    )

    # @-mention references chosen in the task input. Mirror the ``new_chat``
    # request fields (minus SurfSense product docs) so the run can scope
    # retrieval to the user's selected files / folders / connectors. All
    # optional and additive; a task with no mentions behaves as before.
    mentioned_document_ids: list[int] | None = Field(
        default=None,
        description="Knowledge-base document IDs the task references with @.",
    )
    mentioned_folder_ids: list[int] | None = Field(
        default=None,
        description="Knowledge-base folder IDs the task references with @.",
    )
    mentioned_connector_ids: list[int] | None = Field(
        default=None,
        description="Concrete connector account IDs the task references with @.",
    )
    mentioned_connectors: list[MentionedDocumentInfo] | None = Field(
        default=None,
        description="Display/context metadata for the @-mentioned connector accounts.",
    )
    mentioned_documents: list[MentionedDocumentInfo] | None = Field(
        default=None,
        description=(
            "Chip metadata (id, title, kind, ...) for every @-mention so the "
            "run can resolve titles to virtual paths and substitute them in "
            "the query."
        ),
    )
