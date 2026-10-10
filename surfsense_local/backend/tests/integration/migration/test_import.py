"""Importing a contract-3 export bundle: what the user gets back locally."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from alembic.config import Config
from httpx import AsyncClient, Response
from sqlalchemy import Engine, text

from alembic import command
from modules.chat.models import ChatThread
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from shared.queue import ingest_queue

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[5] / "docs/contracts/export-sample"


@pytest.mark.parametrize("imported_history", [False, True])
async def test_upgrade_then_reimport_preserves_local_and_imported_history(
    client: AsyncClient, engine: Engine, tmp_path: Path, imported_history: bool
) -> None:
    """Local turns do not block recovery; old imported history is not duplicated."""
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[3] / "alembic")
    )
    config.attributes["engine"] = engine
    command.downgrade(config, "0027")
    content = {"text": "My existing turn"}
    if imported_history:
        content["citations"] = []
    created_at = "2026-06-01 10:00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspaces(id, name, cloud_id) VALUES (1, 'Research', 12)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title) "
                "VALUES (1, 1, 'My existing notes')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages("
                "id, chat_thread_id, role, content, created_at, completed_at"
                ") VALUES (1, 1, 'user', :content, :created_at, :completed_at)"
            ),
            {
                "content": json.dumps(content),
                "created_at": created_at,
                "completed_at": created_at if imported_history else None,
            },
        )
    command.upgrade(config, "head")

    response = await import_bundle(client, bundle(tmp_path))

    assert response.status_code == 202
    threads = (await client.get("/workspaces/1/chat/threads")).json()
    expected = ["My existing notes"]
    if not imported_history:
        expected += ["Quick hello", "Why scale the dot product?"]
    assert sorted(thread["title"] for thread in threads) == sorted(expected)
    messages = (await client.get("/chat/threads/1/messages")).json()
    assert [message["content"]["text"] for message in messages] == ["My existing turn"]


async def test_upgrade_then_reimport_claims_an_assistant_only_legacy_thread(
    client: AsyncClient, engine: Engine, tmp_path: Path
) -> None:
    """The old importer's timestamps identify a thread even without a user turn."""
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[3] / "alembic")
    )
    config.attributes["engine"] = engine
    command.downgrade(config, "0027")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspaces(id, name, cloud_id) VALUES (1, 'Research', 12)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title, created_at) "
                "VALUES (1, 1, 'My renamed greeting', '2026-06-03 09:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_messages("
                "id, chat_thread_id, role, content, created_at, completed_at"
                ") VALUES (1, 1, 'assistant', :content, :created_at, :created_at)"
            ),
            {
                "content": json.dumps(
                    {
                        "text": (
                            "Hello. What would you like to look at in this workspace?"
                        ),
                        "citations": [],
                    }
                ),
                "created_at": "2026-06-03 09:00:03",
            },
        )
    command.upgrade(config, "head")
    assistant_only = [
        {
            "id": 502,
            "title": "Quick hello",
            "created_at": "2026-06-03T09:00:00+00:00",
            "messages": [
                {
                    "role": "assistant",
                    "text": "Hello. What would you like to look at in this workspace?",
                    "citations": [],
                    "created_at": "2026-06-03T09:00:03+00:00",
                }
            ],
        }
    ]

    response = await import_bundle(
        client,
        bundle(
            tmp_path,
            replacements={"workspaces/12/chats.json": json.dumps(assistant_only)},
        ),
    )

    assert response.status_code == 202
    threads = (await client.get("/workspaces/1/chat/threads")).json()
    assert [(thread["id"], thread["title"]) for thread in threads] == [
        (1, "My renamed greeting")
    ]
    messages = (await client.get("/chat/threads/1/messages")).json()
    assert [message["role"] for message in messages] == ["assistant"]
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT chat_threads.cloud_id, has_unkeyed_imported_threads "
                "FROM chat_threads JOIN workspaces "
                "ON workspaces.id = chat_threads.workspace_id "
                "WHERE chat_threads.id = 1"
            )
        ).one() == (502, 1)


def bundle(
    tmp_path: Path,
    manifest: dict | None = None,
    *,
    missing: str | None = None,
    replacements: dict[str, str] | None = None,
) -> Path:
    """Zip the committed fixture, optionally with a manifest of the test's own."""
    path = tmp_path / "export.zip"
    replacements = replacements or {}
    with ZipFile(path, "w") as archive:
        if manifest is None:
            archive.write(SAMPLE / "manifest.json", "manifest.json")
        else:
            archive.writestr("manifest.json", json.dumps(manifest))
        for file in sorted(SAMPLE.rglob("*")):
            relative = file.relative_to(SAMPLE).as_posix()
            if file.is_file() and file.name != "manifest.json" and relative != missing:
                if relative in replacements:
                    archive.writestr(relative, replacements[relative])
                else:
                    archive.write(file, relative)
    return path


async def import_bundle(client: AsyncClient, path: Path) -> Response:
    """Post the file the way the renderer's picker will."""
    return await client.post(
        "/migration/import",
        files={"file": ("export.zip", path.read_bytes(), "application/zip")},
    )


async def test_each_exported_workspace_becomes_a_local_one(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A user with two cloud workspaces finds the same two after importing."""
    response = await import_bundle(client, bundle(tmp_path))

    assert response.status_code == 202
    listed = await client.get("/workspaces")
    assert [workspace["name"] for workspace in listed.json()] == ["Research", "Empty"]


async def test_listed_documents_are_created_pending_and_queued(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Only what the manifest lists: OKF index.md and log.md never become documents."""
    response = await import_bundle(client, bundle(tmp_path))
    research = response.json()["workspaces"][0]["id"]

    documents = (await client.get(f"/workspaces/{research}/documents")).json()
    assert sorted(document["title"] for document in documents) == [
        "Notes",
        "Notes",
        "Reading list",
        "Résumé de réunion",
        "index",
    ]
    assert {document["status"] for document in documents} == {"pending"}
    assert sorted(job.args[0] for job in ingest_queue.pending()) == sorted(
        document["id"] for document in documents
    )


async def test_an_imported_document_is_stored_under_its_title(
    client: AsyncClient, tmp_path: Path, data_dir: Path
) -> None:
    """The bundle's Notes_2.md is the export's dedup, not a name the user chose."""
    response = await import_bundle(client, bundle(tmp_path))
    research = response.json()["workspaces"][0]["id"]

    documents = data_dir / "data" / "workspaces" / str(research) / "documents"
    assert sorted(path.name for path in documents.rglob("*") if path.is_file()) == [
        "Notes.md",
        "Notes.md",
        "Reading list.md",
        "Résumé de réunion.md",
        "index.md",
    ]


async def test_threads_arrive_with_their_turns_and_sources_as_text(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Cloud citations cannot be clicked locally, so they are named in the answer."""
    response = await import_bundle(client, bundle(tmp_path))
    research = response.json()["workspaces"][0]["id"]

    threads = (await client.get(f"/workspaces/{research}/chat/threads")).json()
    assert sorted(thread["title"] for thread in threads) == [
        "Quick hello",
        "Why scale the dot product?",
    ]
    scaling = next(t for t in threads if t["title"].startswith("Why"))
    messages = (await client.get(f"/chat/threads/{scaling['id']}/messages")).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"]["text"].endswith("\n\nSources: Notes")
    assert messages[1]["content"]["citations"] == []


@pytest.mark.parametrize(
    "path",
    [
        "workspaces/12/documents/../../../etc/passwd",
        "/workspaces/12/documents/Notes.md",
        "workspaces/13/documents/Notes.md",
        "workspaces\\12\\documents\\Notes.md",
    ],
)
async def test_a_manifest_escaping_the_tree_is_rejected_before_anything_is_written(
    client: AsyncClient, tmp_path: Path, data_dir: Path, path: str
) -> None:
    """The manifest is untrusted input; one bad path fails the whole bundle."""
    manifest = json.loads((SAMPLE / "manifest.json").read_text())
    manifest["workspaces"][0]["documents"][0]["path"] = path

    response = await import_bundle(client, bundle(tmp_path, manifest))

    assert response.status_code == 422
    assert (await client.get("/workspaces")).json() == []
    assert not (data_dir / "data").exists()


async def test_other_formats_and_non_bundles_are_refused(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Only surfsense-export/1; a future format needs a new reader, not a guess."""
    manifest = json.loads((SAMPLE / "manifest.json").read_text())
    manifest["format"] = "surfsense-export/2"
    other_format = await import_bundle(client, bundle(tmp_path, manifest))

    not_a_zip = tmp_path / "notes.md"
    not_a_zip.write_text("# just a file")
    not_a_bundle = await import_bundle(client, not_a_zip)

    assert other_format.status_code == 422
    assert not_a_bundle.status_code == 422
    assert (await client.get("/workspaces")).json() == []


async def test_importing_the_same_bundle_twice_adds_nothing(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Quitting mid-import and running it again must not double the account."""
    first = await import_bundle(client, bundle(tmp_path))
    research = first.json()["workspaces"][0]["id"]
    threads = (await client.get(f"/workspaces/{research}/chat/threads")).json()
    quick_hello = next(thread for thread in threads if thread["title"] == "Quick hello")
    renamed = await client.patch(
        f"/chat/threads/{quick_hello['id']}",
        json={"title": "My quick notes"},
    )

    second = await import_bundle(client, bundle(tmp_path))

    assert renamed.status_code == 200
    assert second.json() == first.json()
    assert len((await client.get("/workspaces")).json()) == 2
    assert len((await client.get(f"/workspaces/{research}/documents")).json()) == 5
    threads = (await client.get(f"/workspaces/{research}/chat/threads")).json()
    assert len(threads) == 2
    assert "My quick notes" in {thread["title"] for thread in threads}
    messages = (await client.get(f"/chat/threads/{quick_hello['id']}/messages")).json()
    assert len(messages) == 2


async def test_reimport_finishes_threads_after_an_interrupted_import(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A workspace committed before its threads is not mistaken for completion."""
    with pytest.raises(KeyError):
        await import_bundle(
            client,
            bundle(tmp_path, missing="workspaces/12/chats.json"),
        )

    workspaces = (await client.get("/workspaces")).json()
    research = next(
        workspace["id"] for workspace in workspaces if workspace["name"] == "Research"
    )
    assert (await client.get(f"/workspaces/{research}/chat/threads")).json() == []

    await import_bundle(client, bundle(tmp_path))

    threads = (await client.get(f"/workspaces/{research}/chat/threads")).json()
    assert sorted(thread["title"] for thread in threads) == [
        "Quick hello",
        "Why scale the dot product?",
    ]


async def test_reimport_preserves_threads_imported_before_they_kept_cloud_ids(
    client: AsyncClient, engine: Engine, tmp_path: Path
) -> None:
    """An upgrade must not copy a user's already imported chat history."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(
            name="Research",
            cloud_id=12,
            has_unkeyed_imported_threads=True,
        )
        session.add(workspace)
        session.flush()
        session.add_all(
            [
                ChatThread(workspace_id=workspace.id, title="Quick hello"),
                ChatThread(
                    workspace_id=workspace.id,
                    title="Why scale the dot product?",
                ),
            ]
        )
        session.commit()
        workspace_id = workspace.id

    await import_bundle(client, bundle(tmp_path))

    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert sorted(thread["title"] for thread in threads) == [
        "Quick hello",
        "Why scale the dot product?",
    ]
