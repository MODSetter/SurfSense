from zipfile import BadZipFile, ZipFile

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError

from api.dependencies import SessionDep
from modules.documents.storage import stream_upload
from modules.migration.schemas import ImportAccepted, ImportedWorkspace, Manifest
from modules.migration.service import find_or_create_workspaces, import_bundle
from shared.config import get_storage_settings

router = APIRouter(prefix="/migration", tags=["migration"])

# Zip-bomb guard, read from the directory before anything is extracted. Sized
# far above any real account (OKF adds index.md and log.md per folder); a
# legitimate bundle that trips it is a bug report, and the fix is these numbers.
MAX_BUNDLE_ENTRIES = 250_000
MAX_BUNDLE_UNPACKED_BYTES = 5 * 1024 * 1024 * 1024


@router.post(
    "/import",
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a SurfSense cloud export bundle",
)
def start_import(
    file: UploadFile,
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
) -> ImportAccepted:
    staged = stream_upload(file, get_storage_settings().data_dir / "imports")
    try:
        with ZipFile(staged.path) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_BUNDLE_ENTRIES
                or sum(entry.file_size for entry in entries) > MAX_BUNDLE_UNPACKED_BYTES
            ):
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE, "bundle is too large to import"
                )
            manifest = Manifest.model_validate_json(archive.read("manifest.json"))
    except (BadZipFile, KeyError, ValidationError) as failure:
        staged.path.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"not a SurfSense export bundle: {failure}",
        ) from failure
    except BaseException:
        staged.path.unlink(missing_ok=True)
        raise

    workspaces = find_or_create_workspaces(session, manifest)
    # Before the background task, which reads these rows through its own session.
    session.commit()

    background.add_task(
        import_bundle,
        request.app.state.session_factory,
        staged.path,
        manifest,
        {
            workspace.cloud_id: (workspace.id, created)
            for workspace, created in workspaces
        },
    )
    return ImportAccepted(
        workspaces=[
            ImportedWorkspace(
                id=workspace.id, cloud_id=workspace.cloud_id, name=workspace.name
            )
            for workspace, _ in workspaces
        ]
    )
