from app.artifacts.keys import build_artifact_file_key
from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole


def test_artifact_file_key_is_scoped_and_preserves_normalized_extension() -> None:
    key = build_artifact_file_key(
        workspace_id=12,
        artifact_id=34,
        role=ArtifactFileRole.PREVIEW,
        filename="Quarterly.Report.PDF",
    )

    prefix, unique_filename = key.rsplit("/", 1)
    assert prefix == "artifacts/12/34/preview"
    assert unique_filename.endswith(".pdf")
    assert len(unique_filename.removesuffix(".pdf")) == 32


def test_artifact_model_is_a_unique_document_sidecar() -> None:
    constraint = next(
        constraint
        for constraint in Artifact.__table__.constraints
        if constraint.name == "uq_artifacts_document_id"
    )
    assert tuple(column.name for column in constraint.columns) == ("document_id",)
    assert Artifact.__table__.c.document_id.nullable is False
    assert Artifact.__table__.c.format.type.__class__.__name__ == "String"
    assert {
        "title",
        "path",
        "search_content",
        "content_hash",
        "indexing_status",
    }.isdisjoint(Artifact.__table__.c.keys())


def test_artifact_files_have_one_role_and_unique_blob_key() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in ArtifactFile.__table__.constraints
        if constraint.name
    }

    assert constraints["uq_artifact_files_artifact_role"] == (
        "artifact_id",
        "role",
    )
    assert constraints["uq_artifact_files_storage_key"] == ("storage_key",)
