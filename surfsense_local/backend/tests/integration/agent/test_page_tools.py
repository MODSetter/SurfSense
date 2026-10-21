"""The page tool as opencode's MCP client calls it: a page the agent wrote, kept as a version in Studio."""

import pytest
from sqlalchemy import Engine

from modules.agent.tool_endpoint import save_page
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.studio_documents.recipe import RECIPE_KEY
from modules.artifacts.web_pages.no_network import NO_NETWORK_POLICY
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401

# The job indexes the page's text; the stub stands in for the embedder.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images"),
]

PAGE = """\
<!doctype html>
<html lang="en">
<head><title>Tab</title><style>h1 { color: teal }</style></head>
<body>
<h1>Q3 revenue</h1>
<p>Revenue rose 12% to 4.2 million.</p>
<script>document.title = "live"</script>
</body>
</html>
"""
META = f'<meta http-equiv="Content-Security-Policy" content="{NO_NETWORK_POLICY}">'


def _write(tools: ToolEndpoint, workspace_id: int, name: str, page: str | bytes) -> str:
    """The page in the thread's outputs folder, and the path the agent names it by."""
    path = tools.folder(workspace_id) / "outputs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(page, bytes):
        path.write_bytes(page)
    else:
        path.write_text(page, encoding="utf-8")
    return f"outputs/{name}"


def _artifact_id(text: str) -> int:
    return int(text.split(",")[0].removeprefix("Rendered artifact "))


def _stored(engine: Engine, artifact_id: int) -> str:
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        primary = next(f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY)
        path = get_storage_settings().data_dir / primary.storage_key
        return path.read_text(encoding="utf-8")


async def _listed(tools: ToolEndpoint, workspace_id: int) -> list[dict]:
    reply = await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    return reply.json()


async def test_a_saved_page_is_a_ready_version_with_its_text(
    tools: ToolEndpoint, studio_worker: None, engine: Engine
) -> None:
    """The model learns the artifact, its version and its opening text, not its code."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3 revenue"}
    )

    assert is_error is False, text
    artifact_id = _artifact_id(text)
    assert (
        text.splitlines()[0]
        == f"Rendered artifact {artifact_id}, version 1: Q3 revenue"
    )
    assert "Revenue rose 12% to 4.2 million." in text
    assert "document.title" not in text
    (listed,) = await _listed(tools, workspace_id)
    assert (listed["format"], listed["status"]) == ("html", "ready")
    assert listed["version"] == {"root_id": artifact_id, "number": 1, "parent_id": None}


async def test_the_stored_page_reaches_no_network(
    tools: ToolEndpoint, studio_worker: None, engine: Engine
) -> None:
    """The policy is stored right after the doctype, ahead of everything the page wrote."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, _ = await tools.call(workspace_id, "save_page", {"path": path, "title": "Q3"})

    assert _stored(engine, _artifact_id(text)).startswith(f"<!doctype html>{META}\n")


async def test_saving_with_its_artifact_id_makes_the_next_version(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """An edit keeps the page: same root, the next number."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)
    first, _ = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )
    root = _artifact_id(first)
    _write(tools, workspace_id, "q3.html", PAGE.replace("12%", "14%"))

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3", "artifact_id": root}
    )

    assert is_error is False, text
    assert text.splitlines()[0].endswith("version 2: Q3")
    assert "Revenue rose 14%" in text
    newest = next(a for a in await _listed(tools, workspace_id) if a["id"] != root)
    assert newest["version"] == {"root_id": root, "number": 2, "parent_id": root}


async def test_a_title_the_thread_saved_again_without_artifact_id_is_refused(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """A weaker model leaving artifact_id out of an edit gets the id, not a second page."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)
    first, _ = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": " q3 "}
    )

    assert is_error is True
    assert f"pass artifact_id {_artifact_id(first)}" in text


@pytest.mark.parametrize(
    ("path", "says"),
    [
        ("sources/q3.html", "under outputs/"),
        ("outputs/../sources/q3.html", "under outputs/"),
        ("/etc/hosts", "under outputs/"),
        ("outputs/missing.html", "There is no file"),
        ("outputs/q3.txt", ".html"),
    ],
)
async def test_a_path_it_may_not_read_is_refused(
    tools: ToolEndpoint, path: str, says: str
) -> None:
    """Only a page under the thread's own outputs/ is saved."""
    workspace_id = await tools.workspace()
    _write(tools, workspace_id, "q3.txt", PAGE)
    (tools.folder(workspace_id) / "sources").mkdir(parents=True, exist_ok=True)
    (tools.folder(workspace_id) / "sources" / "q3.html").write_text(PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is True
    assert says in text


async def test_a_link_out_of_outputs_is_refused(tools: ToolEndpoint) -> None:
    """A link is followed before the check, so it cannot point at a source."""
    workspace_id = await tools.workspace()
    secret = tools.folder(workspace_id) / "sources" / "secret.html"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(PAGE)
    outputs = tools.folder(workspace_id) / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "q3.html").symlink_to(secret)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": "outputs/q3.html", "title": "Q3"}
    )

    assert is_error is True
    assert "under outputs/" in text


@pytest.mark.parametrize(
    ("page", "says"),
    [
        (b"\xff\xfe<p>x</p>", "UTF-8"),
        ("just words, no markup", "no HTML"),
        ("   ", "no HTML"),
    ],
)
async def test_a_file_that_is_no_page_is_refused(
    tools: ToolEndpoint, page: str | bytes, says: str
) -> None:
    """The refusal names what to fix."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", page)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is True
    assert says in text


async def test_a_page_over_the_size_limit_is_refused(
    tools: ToolEndpoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit is the page as stored, its kit included."""
    monkeypatch.setattr(save_page, "PAGE_BYTES", 100)
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is True
    assert "larger than" in text


async def test_the_page_is_stored_as_written_with_only_the_policy_added(
    tools: ToolEndpoint, studio_worker: None, engine: Engine
) -> None:
    """Nothing is written into a page but the no-network policy: its script runs as the agent wrote it."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "lock.html", PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Lock"}
    )

    assert is_error is False, text
    assert _stored(engine, _artifact_id(text)) == PAGE.replace(
        "<!doctype html>", f"<!doctype html>{META}", 1
    )


async def test_outside_resources_are_named_as_blocked_and_links_are_not(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The page is saved; the model is told what the viewer will not load."""
    workspace_id = await tools.workspace()
    page = PAGE.replace(
        "</head>",
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">'
        "<style>body { background: url(https://cdn.example/bg.png) }</style></head>",
    ).replace(
        "</body>",
        '<img src="https://cdn.example/logo.png" alt="Logo">'
        '<a href="https://surfsense.com">Site</a></body>',
    )
    path = _write(tools, workspace_id, "q3.html", page)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is False, text
    assert "https://fonts.googleapis.com/css?family=Inter" in text
    assert "https://cdn.example/bg.png" in text
    assert "https://cdn.example/logo.png" in text
    assert "https://surfsense.com" not in text


async def test_without_the_desktop_app_there_are_no_screenshots_and_it_says_why(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The page is made; only its screenshots are missing."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is False, text
    assert "No screenshots: " in text
    assert "desktop app" in text


async def test_a_page_studio_made_is_not_continued(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Only a page this tool saved takes a next version here."""
    workspace_id = await tools.workspace()
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title="Studio page",
            document_type=DocumentType.ARTIFACT,
            status=DocumentStatus.READY,
        )
        session.add(document)
        session.flush()
        artifact = Artifact(
            document_id=document.id,
            workspace_id=workspace_id,
            format="html",
            artifact_metadata={RECIPE_KEY: {"kind": "draft"}},
        )
        session.add(artifact)
        session.commit()
        studio_id = artifact.id
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, is_error = await tools.call(
        workspace_id,
        "save_page",
        {"path": path, "title": "Q3", "artifact_id": studio_id},
    )

    assert is_error is True
    assert "new page" in text


async def test_studio_is_not_asked_for_a_web_page(tools: ToolEndpoint) -> None:
    """The agent writes its own page, as it renders its own Word document."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id,
        "create_artifact",
        {"format": "html", "source_ids": [1]},
    )

    assert is_error is True
    assert "surfsense_save_page" in text
    assert "surfsense-html" in text


async def test_the_agents_working_file_is_left_as_it_wrote_it(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The policy goes into the stored copy, never into the file it edits."""
    workspace_id = await tools.workspace()
    path = _write(tools, workspace_id, "q3.html", PAGE)

    text, is_error = await tools.call(
        workspace_id, "save_page", {"path": path, "title": "Q3"}
    )

    assert is_error is False, text
    working = tools.folder(workspace_id) / path
    assert working.read_text(encoding="utf-8") == PAGE
