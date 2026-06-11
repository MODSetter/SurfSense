import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import (
    Connection,
    ConnectionScope,
    Model,
    ModelSource,
    Permission,
    SearchSpace,
    User,
    get_async_session,
)
from app.schemas import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionUpdate,
    ModelCreate,
    ModelRead,
    ModelRolesRead,
    ModelRolesUpdate,
    ModelUpdate,
    VerifyConnectionResponse,
)
from app.services.model_connection_service import (
    derive_capabilities,
    discover_models,
    persist_verification,
    test_model,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


def _model_read(model: Model | dict) -> ModelRead:
    return ModelRead.model_validate(model)


def _connection_read(conn: Connection | dict, models: list[Model | dict] | None = None) -> ConnectionRead:
    if isinstance(conn, dict):
        payload = {
            **conn,
            "has_api_key": bool(conn.get("api_key")),
            "api_key": None,
            "models": [_model_read(model) for model in (models or [])],
        }
        payload.pop("api_key", None)
        return ConnectionRead.model_validate(payload)

    return ConnectionRead(
        id=conn.id,
        protocol=conn.protocol,
        native_provider=conn.native_provider,
        base_url=conn.base_url,
        extra=conn.extra or {},
        scope=conn.scope,
        search_space_id=conn.search_space_id,
        user_id=conn.user_id,
        enabled=conn.enabled,
        has_api_key=bool(conn.api_key),
        last_verified_at=conn.last_verified_at,
        last_status=conn.last_status,
        last_error=conn.last_error,
        models=[_model_read(model) for model in (models or [])],
        created_at=conn.created_at,
    )


async def _get_search_space(session: AsyncSession, search_space_id: int) -> SearchSpace:
    result = await session.execute(select(SearchSpace).where(SearchSpace.id == search_space_id))
    search_space = result.scalars().first()
    if not search_space:
        raise HTTPException(status_code=404, detail="Search space not found")
    return search_space


async def _load_connection(session: AsyncSession, connection_id: int) -> Connection:
    result = await session.execute(
        select(Connection)
        .options(selectinload(Connection.models))
        .where(Connection.id == connection_id)
    )
    conn = result.scalars().first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


async def _assert_connection_access(
    session: AsyncSession,
    user: User,
    conn: Connection,
    permission: str = Permission.LLM_CONFIGS_CREATE.value,
) -> None:
    if conn.search_space_id:
        await check_permission(
            session,
            user,
            conn.search_space_id,
            permission,
            "You don't have permission to manage model connections in this search space",
        )
        return
    if conn.user_id != user.id:
        raise HTTPException(status_code=403, detail="Connection does not belong to user")


@router.get("/global-model-connections", response_model=list[ConnectionRead])
async def list_global_connections(user: User = Depends(current_active_user)):
    del user
    models_by_connection: dict[int, list[dict]] = {}
    for model in config.GLOBAL_MODELS:
        models_by_connection.setdefault(model["connection_id"], []).append(model)
    return [
        _connection_read(conn, models_by_connection.get(conn["id"], []))
        for conn in config.GLOBAL_CONNECTIONS
    ]


@router.get("/model-connections", response_model=list[ConnectionRead])
async def list_connections(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    stmt = select(Connection).options(selectinload(Connection.models))
    if search_space_id is not None:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to view model connections in this search space",
        )
        stmt = stmt.where(Connection.search_space_id == search_space_id)
    else:
        stmt = stmt.where(Connection.user_id == user.id)
    result = await session.execute(stmt.order_by(Connection.id))
    return [
        _connection_read(conn, list(conn.models))
        for conn in result.scalars().all()
    ]


@router.post("/model-connections", response_model=ConnectionRead)
async def create_connection(
    data: ConnectionCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if data.scope == ConnectionScope.GLOBAL:
        raise HTTPException(status_code=400, detail="GLOBAL connections are YAML-only")
    if data.scope == ConnectionScope.SEARCH_SPACE:
        if data.search_space_id is None:
            raise HTTPException(status_code=400, detail="search_space_id is required")
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this search space",
        )
    conn = Connection(
        **data.model_dump(exclude={"search_space_id"}),
        search_space_id=data.search_space_id if data.scope == ConnectionScope.SEARCH_SPACE else None,
        user_id=user.id,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return _connection_read(conn, [])


@router.put("/model-connections/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    connection_id: int,
    data: ConnectionUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(session, user, conn, Permission.LLM_CONFIGS_UPDATE.value)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(conn, key, value)
    await session.commit()
    conn = await _load_connection(session, connection_id)
    return _connection_read(conn, list(conn.models))


@router.delete("/model-connections/{connection_id}")
async def delete_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(session, user, conn, Permission.LLM_CONFIGS_DELETE.value)
    await session.delete(conn)
    await session.commit()
    return {"status": "deleted"}


@router.post("/model-connections/{connection_id}/verify", response_model=VerifyConnectionResponse)
async def verify_model_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(session, user, conn, Permission.LLM_CONFIGS_CREATE.value)
    result = await persist_verification(conn)
    await session.commit()
    return VerifyConnectionResponse(status=result.status, ok=result.ok, message=result.message)


@router.post("/model-connections/{connection_id}/discover", response_model=list[ModelRead])
async def discover_connection_models(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(session, user, conn, Permission.LLM_CONFIGS_CREATE.value)
    discovered = await discover_models(conn)
    by_model_id = {model.model_id: model for model in conn.models}
    for item in discovered:
        db_model = by_model_id.get(item["model_id"])
        if db_model is None:
            db_model = Model(
                connection_id=conn.id,
                model_id=item["model_id"],
                display_name=item.get("display_name"),
                source=item["source"],
                capabilities=item["capabilities"],
                capabilities_declared=item["capabilities"],
                capabilities_verified={},
                capabilities_override={},
                enabled=False,
                catalog=item.get("metadata") or {},
            )
            session.add(db_model)
        else:
            db_model.display_name = item.get("display_name") or db_model.display_name
            db_model.capabilities_declared = item["capabilities"]
            db_model.capabilities = {
                **item["capabilities"],
                **(db_model.capabilities_override or {}),
            }
            db_model.catalog = item.get("metadata") or db_model.catalog
    await session.commit()
    conn = await _load_connection(session, connection_id)
    return [_model_read(model) for model in conn.models]


@router.post("/model-connections/{connection_id}/models", response_model=ModelRead)
async def add_manual_model(
    connection_id: int,
    data: ModelCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(session, user, conn, Permission.LLM_CONFIGS_UPDATE.value)

    model_id = data.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
    if any(existing.model_id == model_id for existing in conn.models):
        raise HTTPException(status_code=400, detail="Model already exists on this connection")

    capabilities = derive_capabilities(conn, model_id)
    model = Model(
        connection_id=conn.id,
        model_id=model_id,
        display_name=data.display_name or None,
        source=ModelSource.MANUAL,
        capabilities=capabilities,
        capabilities_declared=capabilities,
        capabilities_verified={},
        capabilities_override={},
        enabled=True,
        catalog={},
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return _model_read(model)


@router.put("/models/{model_id}", response_model=ModelRead)
async def update_model(
    model_id: int,
    data: ModelUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Model).options(selectinload(Model.connection)).where(Model.id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await _assert_connection_access(session, user, model.connection, Permission.LLM_CONFIGS_UPDATE.value)
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(model, key, value)
    if "capabilities_override" in update:
        model.capabilities = {
            **(model.capabilities_declared or {}),
            **(model.capabilities_override or {}),
        }
    await session.commit()
    await session.refresh(model)
    return _model_read(model)


@router.post("/models/{model_id}/test", response_model=VerifyConnectionResponse)
async def test_connection_model(
    model_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Model).options(selectinload(Model.connection)).where(Model.id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await _assert_connection_access(session, user, model.connection, Permission.LLM_CONFIGS_UPDATE.value)
    result = await test_model(model.connection, model)
    await session.commit()
    return VerifyConnectionResponse(status=result.status, ok=result.ok, message=result.message)


@router.get("/search-spaces/{search_space_id}/model-roles", response_model=ModelRolesRead)
async def get_model_roles(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.LLM_CONFIGS_CREATE.value,
        "You don't have permission to view model roles in this search space",
    )
    search_space = await _get_search_space(session, search_space_id)
    return ModelRolesRead(
        chat_model_id=search_space.chat_model_id,
        vision_model_id=search_space.vision_model_id,
        image_gen_model_id=search_space.image_gen_model_id,
    )


@router.put("/search-spaces/{search_space_id}/model-roles", response_model=ModelRolesRead)
async def update_model_roles(
    search_space_id: int,
    data: ModelRolesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.LLM_CONFIGS_UPDATE.value,
        "You don't have permission to update model roles in this search space",
    )
    search_space = await _get_search_space(session, search_space_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(search_space, key, value)
    await session.commit()
    await session.refresh(search_space)
    return ModelRolesRead(
        chat_model_id=search_space.chat_model_id,
        vision_model_id=search_space.vision_model_id,
        image_gen_model_id=search_space.image_gen_model_id,
    )
