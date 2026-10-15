"""Which parts of a selection reach the model, when it outgrows the budget."""

import pytest
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from worker.ingestion import run as ingest
from worker.studio import run
from worker.studio.shared import gather
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.integration

ANSWER = "The probe carried a generator catalogued as RTGX7."
REPLIES = {
    "quiz": '{"title": "T", "questions": []}',
    "summary": "# T\n\nBody.",
}


@pytest.fixture
def session(engine) -> Session:
    """A session on the migrated database the pipeline opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def log(name: str, lines: int, *, answer_at: int | None = None) -> str:
    """A document of distinct lines, one of them the answer if asked."""
    text = [
        f"Line {n} of the {name} log records a routine check." for n in range(lines)
    ]
    if answer_at is not None:
        text[answer_at] = ANSWER
    return "\n".join(text)


def select(session: Session, *contents: str) -> tuple[int, list[int]]:
    """A workspace holding one indexed note per content, in selection order."""
    workspace = Workspace(name="Reports")
    session.add(workspace)
    session.commit()
    ids = []
    for index, content in enumerate(contents):
        note = Document(
            workspace_id=workspace.id,
            title=f"Report {index + 1}",
            document_type=DocumentType.NOTE,
            content=content,
        )
        session.add(note)
        session.commit()
        ingest(note.id)
        ids.append(note.id)
    return workspace.id, ids


def make(
    session: Session, workspace_id: int, ids: list[int], fmt: str, prompt: str | None
) -> Artifact:
    """A pending artifact of `fmt` over the selected notes."""
    document = Document(
        workspace_id=workspace_id,
        title=fmt,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace_id,
        format=fmt,
        artifact_metadata={"source_document_ids": ids, "prompt": prompt},
    )
    session.add(artifact)
    session.commit()
    return artifact


def grounding(monkeypatch: pytest.MonkeyPatch, fmt: str) -> list[list[Source]]:
    """What each model call was grounded on."""
    seen: list[list[Source]] = []

    def fake(_model: object, _system: str, sources: list[Source], **_kw: object):
        seen.append(sources)
        return REPLIES[fmt]

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake)
    return seen


def no_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the selection is searched."""

    def refuse(*_args: object, **_kwargs: object):
        raise AssertionError("retrieve() was called")

    monkeypatch.setattr("shared.search.retrieve", refuse)


def test_a_selection_within_the_budget_is_read_whole_and_never_searched(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Today's behaviour, unchanged: embedding a question would buy nothing."""
    workspace_id, ids = select(session, log("pump", 5), log("valve", 5))
    seen = grounding(monkeypatch, "quiz")
    no_retrieval(monkeypatch)

    run(make(session, workspace_id, ids, "quiz", "pressure").id)

    assert [s.content for s in seen[0]] == [log("pump", 5), log("valve", 5)]


def test_a_large_selection_without_a_prompt_reaches_every_document(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The budget is shared, so the last document is not left out; a short one
    is read whole and what it leaves over goes to the others."""
    monkeypatch.setattr(gather, "BUDGET_CHARS", 3_000)
    # Shares of 1,000 stay in the even-share regime this test is about.
    monkeypatch.setattr(gather, "MIN_SHARE_CHARS", 500)
    short = log("note", 2)
    workspace_id, ids = select(session, log("pump", 60), short, log("valve", 60))
    seen = grounding(monkeypatch, "quiz")

    run(make(session, workspace_id, ids, "quiz", None).id)

    sources = seen[0]
    assert [s.document_id for s in sources] == ids
    assert sources[1].content == short
    assert sources[2].content.startswith("Line 0 of the valve log")
    assert sum(len(s.content) for s in sources) <= 3_000


def test_a_prompt_reaches_its_answer_in_the_middle_of_the_last_document(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The passage that answers the prompt is found wherever it sits, and every
    other document still contributes."""
    monkeypatch.setattr(gather, "BUDGET_CHARS", 3_000)
    # Shares of 1,000 stay in the even-share regime this test is about.
    monkeypatch.setattr(gather, "MIN_SHARE_CHARS", 500)
    workspace_id, ids = select(
        session, log("pump", 60), log("valve", 60), log("probe", 60, answer_at=30)
    )
    seen = grounding(monkeypatch, "quiz")

    run(make(session, workspace_id, ids, "quiz", "RTGX7 generator").id)

    sources = seen[0]
    assert ANSWER in sources[2].content
    assert [s.document_id for s in sources] == ids
    assert sum(len(s.content) for s in sources) <= 3_000


def test_a_summary_reads_each_document_from_its_start_even_with_a_prompt(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A summary reads a document's shape, so passages matching the prompt are
    the wrong cut of it."""
    monkeypatch.setattr(gather, "BUDGET_CHARS", 3_000)
    workspace_id, ids = select(session, log("pump", 60), log("probe", 60, answer_at=30))
    seen = grounding(monkeypatch, "summary")
    no_retrieval(monkeypatch)

    run(make(session, workspace_id, ids, "summary", "RTGX7 generator").id)

    assert [s.content[:22] for s in seen[0]] == [
        "Line 0 of the pump log",
        "Line 0 of the probe lo",
    ]


def test_a_selection_too_big_to_share_takes_its_best_passages(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Below the minimum share, every document cut to a sliver says nothing, so
    the scope's best passages are taken instead and the job records which."""
    monkeypatch.setattr(gather, "BUDGET_CHARS", 3_000)
    logs = [log(f"unit{n}", 60) for n in range(8)]
    workspace_id, ids = select(
        session, *logs, log("probe", 60, answer_at=30), log("pump", 60)
    )
    seen = grounding(monkeypatch, "quiz")

    artifact = make(session, workspace_id, ids, "quiz", "RTGX7 generator")
    run(artifact.id)

    sources = seen[0]
    assert sum(len(s.content) for s in sources) <= 3_000
    assert any(ANSWER in s.content for s in sources)
    session.refresh(artifact)
    grounded = artifact.artifact_metadata["grounded_document_ids"]
    assert grounded == [s.document_id for s in sources]
    assert ids[8] in grounded
    assert len(grounded) < len(ids)


def test_a_selection_read_whole_records_every_source_as_grounding(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selection read whole records every source as grounding."""
    workspace_id, ids = select(session, log("pump", 5), log("valve", 5))
    grounding(monkeypatch, "quiz")

    artifact = make(session, workspace_id, ids, "quiz", None)
    run(artifact.id)

    session.refresh(artifact)
    assert artifact.artifact_metadata["grounded_document_ids"] == ids


def test_a_budget_passed_in_is_honoured(session: Session, stub_model: None) -> None:
    """The model's own profile can set the budget; the default is 24,000."""
    _, ids = select(session, log("pump", 60), log("valve", 60))

    sources = gather.gather(session, ids, None, budget_chars=1_000)

    assert sum(len(s.content) for s in sources) <= 1_000
