"""API routes for folder CRUD, move, reorder, and document move operations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Document, Folder, Permission, User, get_async_session
from app.schemas import (
    BulkDocumentMove,
    DocumentMove,
    FolderBreadcrumb,
    FolderCreate,
    FolderMove,
    FolderRead,
    FolderReorder,
    FolderUpdate,
)
from app.services.folder_service import (
    check_no_circular_reference,
    generate_folder_position,
    get_folder_subtree_ids,
    get_subtree_max_depth,
    validate_folder_depth,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


@router.post("/folders", response_model=FolderRead)
async def create_folder(
    request: FolderCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create a new folder. Requires DOCUMENTS_CREATE permission."""
    try:
        await check_permission(
            session,
            user,
            request.search_space_id,
            Permission.DOCUMENTS_CREATE.value,
            "You don't have permission to create folders in this search space",
        )

        if request.parent_id is not None:
            parent = await session.get(Folder, request.parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            if parent.search_space_id != request.search_space_id:
                raise HTTPException(
                    status_code=400,
                    detail="Parent folder belongs to a different search space",
                )

        await validate_folder_depth(session, request.parent_id)

        position = await generate_folder_position(
            session, request.search_space_id, request.parent_id
        )

        folder = Folder(
            name=request.name,
            position=position,
            parent_id=request.parent_id,
            search_space_id=request.search_space_id,
            created_by_id=user.id,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        if "uq_folder_space_parent_name" in str(e):
            raise HTTPException(
                status_code=409,
                detail="A folder with this name already exists at this location",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Failed to create folder: {e!s}"
        ) from e


@router.get("/folders", response_model=list[FolderRead])
async def list_folders(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List all folders in a search space (flat). Requires DOCUMENTS_READ permission."""
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read folders in this search space",
        )

        result = await session.execute(
            select(Folder)
            .where(Folder.search_space_id == search_space_id)
            .order_by(Folder.position)
        )
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list folders: {e!s}"
        ) from e


@router.get("/folders/{folder_id}", response_model=FolderRead)
async def get_folder(
    folder_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a single folder. Requires DOCUMENTS_READ permission."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read folders in this search space",
        )

        return folder

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get folder: {e!s}"
        ) from e


@router.get("/folders/{folder_id}/breadcrumb", response_model=list[FolderBreadcrumb])
async def get_folder_breadcrumb(
    folder_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get ancestor chain for breadcrumb display. Requires DOCUMENTS_READ permission."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read folders in this search space",
        )

        result = await session.execute(
            text("""
                WITH RECURSIVE ancestors AS (
                    SELECT id, name, parent_id, 0 AS depth
                    FROM folders WHERE id = :folder_id
                    UNION ALL
                    SELECT f.id, f.name, f.parent_id, a.depth + 1
                    FROM folders f JOIN ancestors a ON f.id = a.parent_id
                )
                SELECT id, name FROM ancestors ORDER BY depth DESC;
            """),
            {"folder_id": folder_id},
        )
        rows = result.fetchall()
        return [FolderBreadcrumb(id=row.id, name=row.name) for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get breadcrumb: {e!s}"
        ) from e


@router.patch("/folders/{folder_id}/watched")
async def stop_watching_folder(
    folder_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Clear the watched flag from a folder's metadata."""
    folder = await session.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    await check_permission(
        session,
        user,
        folder.search_space_id,
        Permission.DOCUMENTS_UPDATE.value,
        "You don't have permission to update folders in this search space",
    )

    if folder.folder_metadata and isinstance(folder.folder_metadata, dict):
        updated = {**folder.folder_metadata, "watched": False}
        folder.folder_metadata = updated
    await session.commit()

    return {"message": "Folder watch status updated"}


@router.put("/folders/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: int,
    request: FolderUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Rename a folder. Requires DOCUMENTS_UPDATE permission."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to update folders in this search space",
        )

        folder.name = request.name
        await session.commit()
        await session.refresh(folder)
        return folder

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        if "uq_folder_space_parent_name" in str(e):
            raise HTTPException(
                status_code=409,
                detail="A folder with this name already exists at this location",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Failed to update folder: {e!s}"
        ) from e


@router.put("/folders/{folder_id}/move", response_model=FolderRead)
async def move_folder(
    folder_id: int,
    request: FolderMove,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Move a folder to a new parent. Requires DOCUMENTS_UPDATE permission."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to move folders in this search space",
        )

        if request.new_parent_id is not None:
            new_parent = await session.get(Folder, request.new_parent_id)
            if not new_parent:
                raise HTTPException(
                    status_code=404, detail="Target parent folder not found"
                )
            if new_parent.search_space_id != folder.search_space_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move folder to a different search space",
                )

        await check_no_circular_reference(session, folder_id, request.new_parent_id)
        subtree_depth = await get_subtree_max_depth(session, folder_id)
        await validate_folder_depth(session, request.new_parent_id, subtree_depth)

        position = await generate_folder_position(
            session, folder.search_space_id, request.new_parent_id
        )
        folder.parent_id = request.new_parent_id
        folder.position = position
        await session.commit()
        await session.refresh(folder)
        return folder

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        if "uq_folder_space_parent_name" in str(e):
            raise HTTPException(
                status_code=409,
                detail="A folder with this name already exists at the target location",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Failed to move folder: {e!s}"
        ) from e


@router.put("/folders/{folder_id}/reorder", response_model=FolderRead)
async def reorder_folder(
    folder_id: int,
    request: FolderReorder,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Reorder a folder among its siblings via fractional indexing. Requires DOCUMENTS_UPDATE."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to reorder folders in this search space",
        )

        position = await generate_folder_position(
            session,
            folder.search_space_id,
            folder.parent_id,
            before_position=request.before_position,
            after_position=request.after_position,
        )
        folder.position = position
        await session.commit()
        await session.refresh(folder)
        return folder

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to reorder folder: {e!s}"
        ) from e


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete a folder and cascade-delete subfolders. Documents are async-deleted via Celery."""
    try:
        folder = await session.get(Folder, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        await check_permission(
            session,
            user,
            folder.search_space_id,
            Permission.DOCUMENTS_DELETE.value,
            "You don't have permission to delete folders in this search space",
        )

        subtree_ids = await get_folder_subtree_ids(session, folder_id)

        doc_result = await session.execute(
            select(Document.id).where(
                Document.folder_id.in_(subtree_ids),
                Document.status["state"].as_string() != "deleting",
            )
        )
        document_ids = list(doc_result.scalars().all())

        if document_ids:
            await session.execute(
                Document.__table__.update()
                .where(Document.id.in_(document_ids))
                .values(status={"state": "deleting"})
            )
            await session.commit()

        await session.execute(Folder.__table__.delete().where(Folder.id == folder_id))
        await session.commit()

        if document_ids:
            try:
                from app.tasks.celery_tasks.document_tasks import (
                    delete_folder_documents_task,
                )

                delete_folder_documents_task.delay(document_ids)
            except Exception as err:
                await session.execute(
                    Document.__table__.update()
                    .where(Document.id.in_(document_ids))
                    .values(status={"state": "ready"})
                )
                await session.commit()
                raise HTTPException(
                    status_code=503,
                    detail="Folder deleted but document cleanup could not be queued. Documents have been restored.",
                ) from err

        return {
            "message": "Folder deleted successfully",
            "documents_queued_for_deletion": len(document_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete folder: {e!s}"
        ) from e


@router.put("/documents/{document_id}/move")
async def move_document(
    document_id: int,
    request: DocumentMove,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Move a document to a folder (or root). Requires DOCUMENTS_UPDATE permission."""
    try:
        result = await session.execute(
            select(Document).filter(Document.id == document_id)
        )
        document = result.scalars().first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        await check_permission(
            session,
            user,
            document.search_space_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to move documents in this search space",
        )

        if request.folder_id is not None:
            target = await session.get(Folder, request.folder_id)
            if not target:
                raise HTTPException(status_code=404, detail="Target folder not found")
            if target.search_space_id != document.search_space_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move document to a folder in a different search space",
                )

        document.folder_id = request.folder_id
        await session.commit()
        return {"message": "Document moved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to move document: {e!s}"
        ) from e


@router.put("/documents/bulk-move")
async def bulk_move_documents(
    request: BulkDocumentMove,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Move multiple documents to a folder (or root). Requires DOCUMENTS_UPDATE permission."""
    try:
        if not request.document_ids:
            raise HTTPException(status_code=400, detail="No document IDs provided")

        result = await session.execute(
            select(Document).filter(Document.id.in_(request.document_ids))
        )
        documents = result.scalars().all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found")

        search_space_ids = {doc.search_space_id for doc in documents}
        for ss_id in search_space_ids:
            await check_permission(
                session,
                user,
                ss_id,
                Permission.DOCUMENTS_UPDATE.value,
                "You don't have permission to move documents in this search space",
            )

        if request.folder_id is not None:
            target = await session.get(Folder, request.folder_id)
            if not target:
                raise HTTPException(status_code=404, detail="Target folder not found")
            mismatched = [
                doc.id
                for doc in documents
                if doc.search_space_id != target.search_space_id
            ]
            if mismatched:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move documents to a folder in a different search space",
                )

        await session.execute(
            Document.__table__.update()
            .where(Document.id.in_(request.document_ids))
            .values(folder_id=request.folder_id)
        )
        await session.commit()
        return {"message": f"{len(request.document_ids)} documents moved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to move documents: {e!s}"
        ) from e
