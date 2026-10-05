"""Create a document script's artifact: v1 of a new document, or its next version."""

import logging

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.spec import (
    DOCUMENT_FORMATS,
    FORMAT_NAMES,
    DocumentFormat,
    DocumentScript,
    document_script,
)
from modules.artifacts.script_documents.template_source import (
    TemplateRefusedError,
    template_file,
)
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
    version_of,
)
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures import figure_file, parse_figure_name
from modules.embedding.active import EmbeddingNotChosenError, require_active_index
from modules.workspaces.models import Workspace

logger = logging.getLogger(__name__)

TITLE_CHARS = 200
SCRIPT_CHARS = 200_000


class ScriptDocumentRefusedError(Exception):
    """A request this service will not carry out, in a sentence the caller passes on."""


def create_script_document(
    session: Session,
    workspace: Workspace,
    *,
    title: str,
    format: DocumentFormat,
    script: str,
    base_artifact_id: int | None,
    image_names: list[str],
    template_source_id: int | None = None,
) -> Artifact:
    """Keep the script as a pending artifact's spec and queue Studio's job to run it.

    A next version left without `template_source_id` keeps its base's template.
    Commits before enqueueing: the worker is another process and must find the row.
    """
    title = title.strip()
    if not 1 <= len(title) <= TITLE_CHARS:
        raise ScriptDocumentRefusedError(
            f"Give the document a title of 1 to {TITLE_CHARS} characters."
        )
    if format not in DOCUMENT_FORMATS:
        raise ScriptDocumentRefusedError("The format must be docx, pdf, pptx or xlsx.")
    if not script.strip() or len(script) > SCRIPT_CHARS:
        raise ScriptDocumentRefusedError(
            f"Give a script of 1 to {SCRIPT_CHARS:,} characters."
        )
    # The job indexes what the script wrote; failing there would run the script twice.
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise ScriptDocumentRefusedError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error

    images = tuple(dict.fromkeys(image_names))
    source_ids = _image_sources(session, workspace.id, images)
    base = (
        None
        if base_artifact_id is None
        else _base_version(session, workspace.id, base_artifact_id, format)
    )
    template = _template(
        session, workspace.id, format, template_source_id, base_artifact_id
    )
    if template is not None and template not in source_ids:
        source_ids.append(template)

    document = Document(
        workspace_id=workspace.id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id, workspace_id=workspace.id, format=format
    )
    session.add(artifact)
    session.flush()

    version = (
        ArtifactVersion(root=artifact.id, number=1, parent=None)
        if base is None
        else ArtifactVersion(
            root=base.root,
            number=next_version_number(session, workspace.id, base.root),
            parent=base_artifact_id,
        )
    )
    artifact.artifact_metadata = {
        "spec": DocumentScript(
            text=script, format=format, images=images, template_source_id=template
        ).as_metadata(),
        "version": version.as_metadata(),
        "source_document_ids": source_ids,
        "prompt": None,
    }
    session.commit()
    studio_job(artifact.id)
    logger.info(
        "studio: enqueued script document %s format=%s root=%s v%s",
        artifact.id,
        format,
        version.root,
        version.number,
    )
    return artifact


def _image_sources(
    session: Session, workspace_id: int, names: tuple[str, ...]
) -> list[int]:
    """The sources the named figures come from, refusing a name none of them has."""
    for name in names:
        try:
            figure_file(session, workspace_id, name)
        except LookupError as error:
            raise ScriptDocumentRefusedError(
                f'No source in this workspace has an image named "{name}".'
            ) from error
    # figure_file accepted each name, so each parses.
    return list(dict.fromkeys(parse_figure_name(name)[0] for name in names))


def _base_version(
    session: Session, workspace_id: int, base_id: int, format: DocumentFormat
) -> ArtifactVersion:
    base = session.get(Artifact, base_id)
    if base is None or base.workspace_id != workspace_id:
        raise ScriptDocumentRefusedError(
            f"There is no artifact {base_id} in this workspace."
        )
    version = version_of(base.artifact_metadata)
    if version is None:
        raise ScriptDocumentRefusedError(
            f"Artifact {base_id} was not made from a document script, so it has no "
            "versions to continue."
        )
    # Studio's Markdown, or a Refine not written yet: Refine rewrites those (07, decision 8).
    if document_script(base.artifact_metadata) is None:
        raise ScriptDocumentRefusedError(
            f"Artifact {base_id} was made by Studio and keeps no script, so it has "
            "no script to change here. Make a new document without artifact_id, or "
            "tell the user to refine it in Studio."
        )
    # The version switcher shows one document; a PDF of it is a document of its own.
    if base.format != format:
        raise ScriptDocumentRefusedError(
            f"Artifact {base_id} is a {FORMAT_NAMES[base.format]}; a "
            f"{FORMAT_NAMES[format]} starts its own document, made without a base "
            "artifact."
        )
    return version


def inherited_template(
    session: Session, workspace_id: int, base_artifact_id: int | None
) -> int | None:
    """The template source a next version keeps when its call names none."""
    if base_artifact_id is None:
        return None
    base = session.get(Artifact, base_artifact_id)
    if base is None or base.workspace_id != workspace_id:
        return None
    script = document_script(base.artifact_metadata)
    return script.template_source_id if script is not None else None


def _template(
    session: Session,
    workspace_id: int,
    format: DocumentFormat,
    named: int | None,
    base_artifact_id: int | None,
) -> int | None:
    """The template this version starts from: the one named, else its base's; checked either way."""
    source_id = (
        named
        if named is not None
        else inherited_template(session, workspace_id, base_artifact_id)
    )
    if source_id is None:
        return None
    try:
        template_file(session, workspace_id, source_id, format)
    except TemplateRefusedError as refused:
        if named is not None:
            raise ScriptDocumentRefusedError(str(refused)) from refused
        raise ScriptDocumentRefusedError(
            f"Artifact {base_artifact_id} was made from template source "
            f"{source_id}. {refused} Pass another template_source_id, or make a "
            "new document without artifact_id."
        ) from refused
    return source_id
