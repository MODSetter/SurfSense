from collections.abc import Iterator
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures import list_figures
from modules.documents.tasks import extract_figures
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the worker opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def workspace(session: Session) -> Workspace:
    """The workspace a request is made in."""
    created = Workspace(name="Proposals")
    session.add(created)
    session.commit()
    return created


@pytest.fixture
def logo_source(session: Session, workspace: Workspace) -> Document:
    """A logo uploaded as a source and ingested before figures were kept."""
    source = Document(
        workspace_id=workspace.id,
        title="Logo.png",
        document_type=DocumentType.FILE,
        status=DocumentStatus.READY,
        content="Halvorsen Freight logo",
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    logo = BytesIO()
    Image.new("RGB", (40, 20), "red").save(logo, format="PNG")
    (folder / "Logo.png").write_bytes(logo.getvalue())
    return source


@pytest.fixture
def source_figure(session: Session, logo_source: Document) -> str:
    """The name of the one figure the logo source holds, kept by the figures pass."""
    extract_figures.call_local(logo_source.id)
    (figure,) = list_figures(session, logo_source.workspace_id, logo_source.id)
    return figure.name
