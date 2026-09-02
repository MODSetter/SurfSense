import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi import Response
from starlette.requests import Request

from app.artifacts.persistence import ArtifactFileRole
from app.db import Permission
from app.routes import artifacts_routes

USER_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_2 = UUID("00000000-0000-0000-0000-000000000002")


def _flashcard_deck() -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "title": "Deck",
            "cards": [
                {
                    "front_text": f"Question {index}",
                    "back_text": f"Answer {index}",
                }
                for index in range(1, 16)
            ],
        }
    ).encode()


def _quiz() -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "title": "Quiz",
            "questions": [
                {
                    "question_text": f"Question {index}",
                    "options": [f"A {index}", f"B {index}", f"C {index}", f"D {index}"],
                    "correct_option_index": index % 4,
                    "explanation_text": f"Explanation {index}",
                }
                for index in range(5)
            ],
        }
    ).encode()


def _request(
    if_none_match: str | None = None, *, range_header: str | None = None
) -> Request:
    headers = []
    if if_none_match:
        headers.append((b"if-none-match", if_none_match.encode()))
    if range_header:
        headers.append((b"range", range_header.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _file(file_id: int, role: ArtifactFileRole):
    return SimpleNamespace(
        id=file_id,
        role=role,
        original_filename=f"{role.value}.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_backend="local",
        storage_key=f"key-{file_id}",
        checksum_sha256="abc123",
    )


def test_artifact_filename_is_title_based_and_does_not_duplicate_extension():
    assert (
        artifacts_routes._artifact_filename("Quarterly Report.pdf", "revised.pdf")
        == "Quarterly Report.pdf"
    )


def test_artifact_filename_uses_physical_extension():
    assert artifacts_routes._artifact_filename("Strategy.PNG", "revised.png") == (
        "Strategy.png"
    )
    assert artifacts_routes._artifact_filename("Strategy", "revised.png") == (
        "Strategy.png"
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=4-", (4, 9)),
        ("bytes=-3", (7, 9)),
        ("bytes=1-99", (1, 9)),
    ],
)
def test_range_parser_supports_video_request_shapes(header, expected):
    assert artifacts_routes._parse_range(header, 10) == expected


def test_range_parser_rejects_multiple_ranges():
    with pytest.raises(ValueError, match="Multiple"):
        artifacts_routes._parse_range("bytes=1-2,7-8", 10)


def _row_result(row):
    result = SimpleNamespace(first=lambda: row)
    session = AsyncMock()
    session.execute.return_value = result
    return session


def _rows_result(rows):
    result = SimpleNamespace(all=lambda: rows)
    session = AsyncMock()
    session.execute.return_value = result
    return session


async def _body(response) -> bytes:
    return b"".join([chunk async for chunk in response.body_iterator])


@pytest.mark.asyncio
async def test_manifest_is_format_blind_and_orders_durable_files(monkeypatch):
    check = AsyncMock()
    monkeypatch.setattr(artifacts_routes, "check_permission", check)
    artifact = SimpleNamespace(
        id=7,
        format="xlsx",
        generation=3,
        artifact_metadata={"legacy": {"kind": "image", "id": 99}},
        updated_at=None,
        files=[
            _file(2, ArtifactFileRole.PREVIEW),
            _file(1, ArtifactFileRole.PRIMARY),
        ],
    )
    document = SimpleNamespace(
        id=9,
        title="Workbook",
        content_hash="hash",
        source_markdown="# Workbook",
        content="# Workbook",
    )
    session = _row_result((artifact, document))

    result = await artifacts_routes.get_artifact_manifest(
        2, 7, _request(), Response(), session, SimpleNamespace()
    )

    assert result["format"] == "xlsx"
    assert result["document_id"] == 9
    assert result["markdown_representation"] == "# Workbook"
    assert result["legacy"] == {"kind": "image", "id": 99}
    assert [file["role"] for file in result["files"]] == ["primary", "preview"]
    check.assert_awaited_once()
    assert check.await_args.args[3] == Permission.ARTIFACTS_READ.value


@pytest.mark.asyncio
async def test_manifest_honors_generation_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(
        id=7,
        format="markdown",
        generation=3,
        updated_at=None,
        files=[],
    )
    document = SimpleNamespace(
        id=9,
        title="Artifact",
        content_hash="hash",
        source_markdown="body",
        content="body",
    )
    session = _row_result((artifact, document))

    response = await artifacts_routes.get_artifact_manifest(
        2, 7, _request('"hash:3"'), Response(), session, SimpleNamespace()
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "private, no-cache"


@pytest.mark.asyncio
async def test_flashcard_manifest_sanitizes_progress_and_varies_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "deck.json"
    primary.mime_type = "application/json"
    deck = _flashcard_deck()

    async def stream(_record):
        yield deck

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    artifact = SimpleNamespace(
        id=7,
        format="flashcards",
        generation=3,
        artifact_metadata={
            "flashcards": {
                "study_by_user": {
                    str(USER_1): {
                        "generation": 3,
                        "marks": {"0": "good", "15": "again", "bad": "good"},
                        "order": list(range(15)),
                    },
                    str(USER_2): {
                        "generation": 3,
                        "marks": {"1": "again"},
                        "order": list(reversed(range(15))),
                    },
                }
            }
        },
        updated_at=None,
        files=[primary],
    )
    document = SimpleNamespace(
        id=9,
        title="Deck",
        content_hash="hash",
        source_markdown="# Deck",
        content="# Deck",
    )
    session = _row_result((artifact, document))
    response = Response()

    result = await artifacts_routes.get_artifact_manifest(
        2,
        7,
        _request(),
        response,
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result["flashcard_study_state"] == {
        "generation": 3,
        "marks": {"0": "good"},
        "order": list(range(15)),
    }
    assert response.headers["etag"].startswith('"hash:3:')


@pytest.mark.asyncio
async def test_flashcard_progress_patch_updates_bounded_namespace(monkeypatch):
    check = AsyncMock()
    monkeypatch.setattr(artifacts_routes, "check_permission", check)
    mark_updated_at = Mock()
    monkeypatch.setattr(artifacts_routes, "flag_modified", mark_updated_at)
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "deck.json"
    primary.mime_type = "application/json"
    deck = _flashcard_deck()

    async def stream(_record):
        yield deck

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    updated_at = object()
    artifact = SimpleNamespace(
        id=7,
        format="flashcards",
        generation=3,
        artifact_metadata={"verification": {"verified": True}},
        updated_at=updated_at,
        files=[primary],
    )
    session = AsyncMock()
    session.scalar.side_effect = [artifact, artifact]

    result = await artifacts_routes.update_flashcard_progress(
        2,
        7,
        artifacts_routes.FlashcardProgressUpdate(
            generation=3,
            card_index=1,
            mark="again",
        ),
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result == {
        "generation": 3,
        "marks": {"1": "again"},
        "order": list(range(15)),
    }
    assert artifact.artifact_metadata["verification"] == {"verified": True}
    assert (
        artifact.artifact_metadata["flashcards"]["study_by_user"][str(USER_1)] == result
    )
    assert artifact.updated_at is updated_at
    mark_updated_at.assert_called_once_with(artifact, "updated_at")
    session.commit.assert_awaited_once()
    assert check.await_args.args[3] == Permission.ARTIFACTS_UPDATE.value


@pytest.mark.asyncio
async def test_flashcard_progress_patch_rejects_stale_generation(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace(
        id=7,
        format="flashcards",
        generation=4,
        files=[],
    )

    with pytest.raises(artifacts_routes.HTTPException) as error:
        await artifacts_routes.update_flashcard_progress(
            2,
            7,
            artifacts_routes.FlashcardProgressUpdate(
                generation=3,
                card_index=0,
                mark="good",
            ),
            session,
            SimpleNamespace(user=SimpleNamespace(id=USER_1)),
        )

    assert error.value.status_code == 409
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_flashcard_progress_reset_clears_marks_and_preserves_metadata(
    monkeypatch,
):
    check = AsyncMock()
    monkeypatch.setattr(artifacts_routes, "check_permission", check)
    mark_updated_at = Mock()
    monkeypatch.setattr(artifacts_routes, "flag_modified", mark_updated_at)
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "deck.json"
    primary.mime_type = "application/json"

    async def stream(_record):
        yield _flashcard_deck()

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    updated_at = object()
    artifact = SimpleNamespace(
        id=7,
        format="flashcards",
        generation=3,
        artifact_metadata={
            "verification": {"verified": True},
            "flashcards": {
                "study_by_user": {
                    str(USER_1): {
                        "generation": 3,
                        "marks": {"0": "good"},
                        "order": list(reversed(range(15))),
                    },
                    str(USER_2): {
                        "generation": 3,
                        "marks": {"1": "again"},
                        "order": list(range(15)),
                    },
                },
            },
        },
        updated_at=updated_at,
        files=[primary],
    )
    session = AsyncMock()
    session.scalar.side_effect = [artifact, artifact]

    result = await artifacts_routes.reset_artifact_flashcard_progress(
        2,
        7,
        3,
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result == {
        "generation": 3,
        "marks": {},
        "order": list(reversed(range(15))),
    }
    assert artifact.artifact_metadata == {
        "verification": {"verified": True},
        "flashcards": {
            "study_by_user": {
                str(USER_1): result,
                str(USER_2): {
                    "generation": 3,
                    "marks": {"1": "again"},
                    "order": list(range(15)),
                },
            }
        },
    }
    assert artifact.updated_at is updated_at
    mark_updated_at.assert_called_once_with(artifact, "updated_at")
    session.commit.assert_awaited_once()
    assert check.await_args.args[3] == Permission.ARTIFACTS_UPDATE.value


@pytest.mark.asyncio
async def test_flashcard_shuffle_updates_only_current_user(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    monkeypatch.setattr(artifacts_routes, "flag_modified", Mock())
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "deck.json"
    primary.mime_type = "application/json"

    async def stream(_record):
        yield _flashcard_deck()

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    artifact = SimpleNamespace(
        id=7,
        format="flashcards",
        generation=3,
        artifact_metadata={
            "flashcards": {
                "study_by_user": {
                    str(USER_2): {
                        "generation": 3,
                        "marks": {"1": "again"},
                        "order": list(range(15)),
                    }
                }
            }
        },
        updated_at=None,
        files=[primary],
    )
    session = AsyncMock()
    session.scalar.side_effect = [artifact, artifact]
    order = list(reversed(range(15)))

    result = await artifacts_routes.update_flashcard_order(
        2,
        7,
        artifacts_routes.FlashcardOrderUpdate(generation=3, order=order),
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result == {"generation": 3, "marks": {}, "order": order}
    users = artifact.artifact_metadata["flashcards"]["study_by_user"]
    assert users[str(USER_1)] == result
    assert users[str(USER_2)]["marks"] == {"1": "again"}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quiz_manifest_exposes_only_current_user_state_and_varies_etag(
    monkeypatch,
):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "quiz.json"
    primary.mime_type = "application/json"

    async def stream(_record):
        yield _quiz()

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    artifact = SimpleNamespace(
        id=7,
        format="quiz",
        generation=3,
        artifact_metadata={
            "quiz": {
                "progress_by_user": {
                    str(USER_1): {
                        "generation": 3,
                        "mode": "all",
                        "active_question_indices": [0, 1, 2, 3, 4],
                        "answers": {"0": 0},
                        "skipped_question_indices": [2],
                    },
                    str(USER_2): {
                        "generation": 3,
                        "mode": "all",
                        "active_question_indices": [0, 1, 2, 3, 4],
                        "answers": {"1": 1},
                        "skipped_question_indices": [],
                    },
                }
            }
        },
        updated_at=None,
        files=[primary],
    )
    document = SimpleNamespace(
        id=9,
        title="Quiz",
        content_hash="hash",
        source_markdown="# Quiz",
        content="# Quiz",
    )
    response = Response()

    result = await artifacts_routes.get_artifact_manifest(
        2,
        7,
        _request(),
        response,
        _row_result((artifact, document)),
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result["quiz_state"]["answers"] == {"0": 0}
    assert result["quiz_state"]["skipped_question_indices"] == [2]
    assert str(USER_2) not in json.dumps(result)
    assert response.headers["etag"].startswith('"hash:3:')


@pytest.mark.asyncio
async def test_quiz_answer_updates_bounded_namespace_without_content_timestamp(
    monkeypatch,
):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    mark_updated_at = Mock()
    monkeypatch.setattr(artifacts_routes, "flag_modified", mark_updated_at)
    primary = _file(1, ArtifactFileRole.PRIMARY)
    primary.original_filename = "quiz.json"
    primary.mime_type = "application/json"

    async def stream(_record):
        yield _quiz()

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_stream", stream)
    updated_at = object()
    artifact = SimpleNamespace(
        id=7,
        format="quiz",
        generation=3,
        artifact_metadata={"verification": {"verified": True}},
        updated_at=updated_at,
        files=[primary],
    )
    session = AsyncMock()
    session.scalar.side_effect = [artifact, artifact]

    result = await artifacts_routes.update_quiz_answer(
        2,
        7,
        artifacts_routes.QuizAnswerUpdate(
            generation=3,
            question_index=1,
            selected_option_index=2,
        ),
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result["answers"] == {"1": 2}
    assert result["skipped_question_indices"] == []
    assert artifact.artifact_metadata["verification"] == {"verified": True}
    assert artifact.updated_at is updated_at
    mark_updated_at.assert_called_once_with(artifact, "updated_at")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quiz_skip_updates_only_authenticated_user(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    monkeypatch.setattr(artifacts_routes, "flag_modified", Mock())
    artifact = SimpleNamespace(
        id=7,
        format="quiz",
        generation=3,
        artifact_metadata=None,
        updated_at=object(),
    )
    quiz = SimpleNamespace(questions=[object()] * 5)
    monkeypatch.setattr(
        artifacts_routes,
        "_lock_quiz_mutation",
        AsyncMock(return_value=(artifact, quiz)),
    )
    session = AsyncMock()

    result = await artifacts_routes.skip_quiz_question(
        2,
        7,
        artifacts_routes.QuizSkipUpdate(generation=3, question_index=1),
        session,
        SimpleNamespace(user=SimpleNamespace(id=USER_1)),
    )

    assert result["skipped_question_indices"] == [1]
    assert str(USER_1) in artifact.artifact_metadata["quiz"]["progress_by_user"]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_reads_title_and_status_from_document(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(
        id=7,
        document_id=9,
        format="pptx",
        generation=2,
        thread_id=11,
        created_at=SimpleNamespace(isoformat=lambda: "created"),
        updated_at=SimpleNamespace(isoformat=lambda: "updated"),
        artifact_metadata=None,
    )
    document = SimpleNamespace(title="Launch deck", status={"state": "processing"})
    session = _rows_result([(artifact, document)])
    response = Response()

    result = await artifacts_routes.list_artifacts(
        2, response, session, SimpleNamespace()
    )

    assert result == [
        {
            "artifact_id": 7,
            "document_id": 9,
            "title": "Launch deck",
            "format": "pptx",
            "generation": 2,
            "indexing_status": "processing",
            "thread_id": 11,
            "created_at": "created",
            "updated_at": "updated",
        }
    ]
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_list_artifacts_includes_legacy_when_present(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    with_legacy = SimpleNamespace(
        id=1,
        document_id=10,
        format="podcast",
        generation=1,
        thread_id=3,
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
        updated_at=None,
        artifact_metadata={"legacy": {"kind": "podcast", "id": 42}},
    )
    without = SimpleNamespace(
        id=2,
        document_id=11,
        format="markdown",
        generation=1,
        thread_id=None,
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-02T00:00:00+00:00"),
        updated_at=None,
        artifact_metadata=None,
    )
    session = _rows_result(
        [
            (with_legacy, SimpleNamespace(title="Episode", status={"state": "ready"})),
            (without, SimpleNamespace(title="Note", status={"state": "pending"})),
        ]
    )

    result = await artifacts_routes.list_artifacts(
        2, Response(), session, SimpleNamespace()
    )

    assert result[0]["legacy"] == {"kind": "podcast", "id": 42}
    assert "legacy" not in result[1]
    assert result[0]["generation"] == 1


@pytest.mark.asyncio
async def test_list_artifacts_can_be_scoped_to_thread(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = _rows_result([])

    await artifacts_routes.list_artifacts(
        2, Response(), session, SimpleNamespace(), thread_id=17
    )

    query = session.execute.await_args.args[0]
    compiled = query.compile(compile_kwargs={"literal_binds": True})
    assert "artifacts.workspace_id = 2" in str(compiled)
    assert "artifacts.thread_id = 17" in str(compiled)


@pytest.mark.asyncio
async def test_markdown_download_reads_document_body_and_disables_cache(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7, files=[])
    document = SimpleNamespace(
        title="Current notes", source_markdown="# Current", content=""
    )
    session = _row_result((artifact, document))

    response = await artifacts_routes.download_artifact(
        2, 7, session, SimpleNamespace()
    )

    assert await _body(response) == b"# Current"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.asyncio
async def test_current_binary_download_is_attachment_even_for_pdf(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7, files=[_file(8, ArtifactFileRole.PRIMARY)])
    document = SimpleNamespace(
        title="AI Agents: Concise Business Report",
        source_markdown="# PDF",
        content="# PDF",
    )
    session = _row_result((artifact, document))

    async def stream():
        yield b"%PDF"

    monkeypatch.setattr(
        artifacts_routes, "open_artifact_file_stream", lambda _record: stream()
    )
    response = await artifacts_routes.download_artifact(
        2, 7, session, SimpleNamespace()
    )

    assert await _body(response) == b"%PDF"
    assert response.headers["cache-control"] == "private, no-store"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert 'filename="AI Agents_ Concise Business Report.pdf"' in disposition
    assert "primary.pdf" not in disposition


@pytest.mark.asyncio
async def test_file_uses_checksum_etag_and_pdf_inline_disposition(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    record = _file(8, ArtifactFileRole.PRIMARY)
    session = AsyncMock()
    session.scalar.return_value = record
    monkeypatch.setattr(
        artifacts_routes,
        "open_artifact_file_stream",
        lambda _record: iter(()),
    )

    response = await artifacts_routes.stream_artifact_file(
        2, 7, 8, _request(), session, SimpleNamespace()
    )

    assert response.headers["etag"] == '"abc123"'
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["content-disposition"].startswith("inline;")


@pytest.mark.asyncio
async def test_html_file_is_attachment_with_nosniff(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    record = _file(8, ArtifactFileRole.PRIMARY)
    record.original_filename = "calculator.html"
    record.mime_type = "text/html"
    session = AsyncMock()
    session.scalar.return_value = record
    monkeypatch.setattr(
        artifacts_routes,
        "open_artifact_file_stream",
        lambda _record: iter(()),
    )

    response = await artifacts_routes.stream_artifact_file(
        2, 7, 8, _request(), session, SimpleNamespace()
    )

    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_file_honors_checksum_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = _file(8, ArtifactFileRole.PRIMARY)

    response = await artifacts_routes.stream_artifact_file(
        2, 7, 8, _request('"abc123"'), session, SimpleNamespace()
    )

    assert response.status_code == 304


@pytest.mark.asyncio
async def test_file_serves_single_byte_range(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    record = _file(8, ArtifactFileRole.PRIMARY)
    session = AsyncMock()
    session.scalar.return_value = record

    async def ranged(_record, start, end):
        assert (start, end) == (2, 5)
        yield b"2345"

    monkeypatch.setattr(artifacts_routes, "open_artifact_file_range", ranged)
    response = await artifacts_routes.stream_artifact_file(
        2,
        7,
        8,
        _request(range_header="bytes=2-5"),
        session,
        SimpleNamespace(),
    )

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["content-length"] == "4"
    assert response.headers["accept-ranges"] == "bytes"
    assert await _body(response) == b"2345"


@pytest.mark.asyncio
async def test_file_rejects_unsatisfiable_range(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = _file(8, ArtifactFileRole.PRIMARY)

    response = await artifacts_routes.stream_artifact_file(
        2,
        7,
        8,
        _request(range_header="bytes=10-"),
        session,
        SimpleNamespace(),
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */10"


@pytest.mark.asyncio
async def test_delete_marks_joined_document_and_dispatches_document_delete(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7)
    document = SimpleNamespace(id=9, status={"state": "ready"})
    session = _row_result((artifact, document))
    from app.tasks.celery_tasks import document_tasks

    delay = Mock()
    monkeypatch.setattr(document_tasks.delete_document_task, "delay", delay)

    response = await artifacts_routes.delete_artifact(2, 7, session, SimpleNamespace())

    assert response.status_code == 204
    assert document.status == {"state": "deleting"}
    session.commit.assert_awaited_once()
    delay.assert_called_once_with(9)


@pytest.mark.asyncio
async def test_video_payload_rewrites_slide_audio_urls(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(
        id=7,
        format="video",
        thread_id=3,
        artifact_metadata={
            "legacy": {"kind": "video", "id": 99},
            "slides": [
                {
                    "slide_number": 1,
                    "title": "Intro",
                    "audio_storage_key": "ws/1/video/99/1.mp3",
                    "duration_in_frames": 120,
                }
            ],
            "scene_codes": [{"slide_number": 1, "code": " cons()", "title": "Intro"}],
        },
        files=[],
    )
    document = SimpleNamespace(title="Deck", id=1)
    session = _row_result((artifact, document))

    result = await artifacts_routes.get_artifact_video(2, 7, session, SimpleNamespace())

    assert result["status"] == "ready"
    assert result["slides"][0]["audio_url"] == (
        "/api/v1/workspaces/2/artifacts/7/slides/1/audio"
    )
    assert "audio_storage_key" not in result["slides"][0]
    assert result["scene_codes"][0]["code"] == " cons()"
