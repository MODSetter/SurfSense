from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.artifacts.models import Artifact


def get_artifact(artifact_id: int, session: SessionDep) -> Artifact:
    """Resolve an artifact by id.

    Not workspace-scoped in the path: a local install has one user, and the
    file and manifest routes are keyed on the artifact alone.
    """
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")

    return artifact


ArtifactDep = Annotated[Artifact, Depends(get_artifact)]
