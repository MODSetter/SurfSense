"""A job run started as the Jobs screen starts one, from a workbook and a policy among the
workspace's sources; it stays pending until a test works it out, as the Studio worker would."""

from io import BytesIO

import openpyxl
from httpx import AsyncClient
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from tests.integration.artifacts.revised_copies.source_files import add_source
from tests.job_pack_samples import JOB

POLICY = "## Access\n\nAccess to client data is granted on a least-privilege basis."


def questionnaire(*questions: str) -> bytes:
    """A requester's workbook: one question a row, a dropdown in each answer cell."""
    asked = questions or ("Do users have the minimum access they need?",)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["Question", "Answer", "Comments"])
    for question in asked:
        sheet.append([question, None, None])
    rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    rule.add(f"B2:B{1 + len(asked)}")
    sheet.add_data_validation(rule)
    data = BytesIO()
    book.save(data)
    return data.getvalue()


def add_policy(session: Session, workspace_id: int, text: str = POLICY) -> int:
    """A ready source to answer from; the session's transaction is ended."""
    policy = Document(
        workspace_id=workspace_id,
        title="Security plan",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=text,
    )
    session.add(policy)
    session.commit()
    return policy.id


async def start_run(
    client: AsyncClient,
    session: Session,
    workspace_id: int,
    workbook: bytes | None = None,
    policy: str = POLICY,
) -> int:
    """The new run's artifact id, started by the route; the job must be unlocked."""
    workbook_id = add_source(
        session, workspace_id, "Questionnaire.xlsx", workbook or questionnaire()
    )
    policy_id = add_policy(session, workspace_id, policy)
    started = await client.post(
        f"/workspaces/{workspace_id}/job-runs",
        json={"job": JOB, "document_id": workbook_id, "source_ids": [policy_id]},
    )
    assert started.status_code == 201, started.text
    return started.json()["artifact_id"]
