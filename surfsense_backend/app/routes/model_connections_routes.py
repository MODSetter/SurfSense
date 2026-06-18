import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import (
    Connection,
    ConnectionScope,
    Model,
    ModelSource,
    NewChatThread,
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
    ModelPreviewRead,
    ModelProviderRead,
    ModelRead,
    ModelRolesRead,
    ModelRolesUpdate,
    ModelsBulkUpdate,
    ModelSelection,
    ModelTestPreview,
    ModelUpdate,
    VerifyConnectionResponse,
)
from app.services.model_capabilities import has_capability
from app.services.model_connection_service import (
    ModelDiscoveryError,
    derive_capabilities,
    discover_models,
    test_model,
    verify_connection,
)
from app.services.provider_registry import REGISTRY
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()
logger = logging.getLogger(__name__)


def _model_read(model: Model | dict) -> ModelRead:
    return ModelRead.model_validate(model)


def _preview_model_read(item: dict) -> ModelPreviewRead:
    return ModelPreviewRead(
        model_id=item["model_id"],
        display_name=item.get("display_name"),
        source=item.get("source", ModelSource.DISCOVERED),
        supports_chat=item.get("supports_chat"),
        max_input_tokens=item.get("max_input_tokens"),
        supports_image_input=item.get("supports_image_input"),
        supports_tools=item.get("supports_tools"),
        supports_image_generation=item.get("supports_image_generation"),
        enabled=item.get("enabled", False),
        metadata=item.get("metadata") or item.get("catalog") or {},
    )


def _connection_read(
    conn: Connection | dict, models: list[Model | dict] | None = None
) -> ConnectionRead:
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
        provider=conn.provider,
        base_url=conn.base_url,
        api_key=conn.api_key,
        extra=conn.extra or {},
        scope=conn.scope,
        search_space_id=conn.search_space_id,
        user_id=conn.user_id,
        enabled=conn.enabled,
        has_api_key=bool(conn.api_key),
        models=[_model_read(model) for model in (models or [])],
        created_at=conn.created_at,
    )


def _apply_model_facts(model: Model, facts: dict) -> None:
    model.supports_chat = facts.get("supports_chat")
    model.max_input_tokens = facts.get("max_input_tokens")
    model.supports_image_input = facts.get("supports_image_input")
    model.supports_tools = facts.get("supports_tools")
    model.supports_image_generation = facts.get("supports_image_generation")


def _complete_selection_facts(conn: Connection, selection: ModelSelection) -> dict:
    facts = selection.model_dump()
    derived = derive_capabilities(conn, selection.model_id.strip(), selection.metadata)
    for key, value in derived.items():
        if facts.get(key) is None:
            facts[key] = value
    return facts


def _selection_to_model(conn: Connection, selection: ModelSelection) -> Model:
    source = (
        selection.source
        if isinstance(selection.source, ModelSource)
        else ModelSource(selection.source)
    )
    model = Model(
        connection_id=conn.id,
        model_id=selection.model_id.strip(),
        display_name=selection.display_name,
        source=source,
        capabilities_override={},
        enabled=selection.enabled,
        catalog=selection.metadata,
    )
    _apply_model_facts(model, _complete_selection_facts(conn, selection))
    return model


def _default_model_for(models: list[Model], capability: str) -> int | None:
    for model in models:
        if model.enabled and has_capability(model, capability):
            return model.id
    return None


async def _load_role_model(
    session: AsyncSession,
    search_space_id: int,
    model_id: int,
) -> Model | dict | None:
    if model_id < 0:
        return next(
            (model for model in config.GLOBAL_MODELS if model.get("id") == model_id),
            None,
        )

    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .where(Model.id == model_id)
    )
    model = result.scalars().first()
    if model is None or model.connection.search_space_id != search_space_id:
        return None
    return model


def _role_model_enabled(model: Model | dict) -> bool:
    if isinstance(model, dict):
        return bool(model.get("enabled", True))
    return bool(model.enabled and model.connection.enabled)


async def _validate_role_model_id(
    session: AsyncSession,
    *,
    search_space_id: int,
    model_id: int | None,
    capability: str,
) -> int:
    if model_id is None or model_id == 0:
        return 0

    model = await _load_role_model(session, search_space_id, model_id)
    if model and _role_model_enabled(model) and has_capability(model, capability):
        return model_id

    raise HTTPException(
        status_code=400,
        detail=f"Selected model is not available for {capability}",
    )


async def _resolve_role_model_id(
    session: AsyncSession,
    *,
    search_space_id: int,
    model_id: int | None,
    capability: str,
) -> int:
    try:
        return await _validate_role_model_id(
            session,
            search_space_id=search_space_id,
            model_id=model_id,
            capability=capability,
        )
    except HTTPException:
        return 0


async def _clear_invalid_roles(
    session: AsyncSession, search_space_id: int
) -> SearchSpace:
    search_space = await _get_search_space(session, search_space_id)
    search_space.chat_model_id = await _resolve_role_model_id(
        session,
        search_space_id=search_space_id,
        model_id=search_space.chat_model_id,
        capability="chat",
    )
    search_space.vision_model_id = await _resolve_role_model_id(
        session,
        search_space_id=search_space_id,
        model_id=search_space.vision_model_id,
        capability="vision",
    )
    search_space.image_gen_model_id = await _resolve_role_model_id(
        session,
        search_space_id=search_space_id,
        model_id=search_space.image_gen_model_id,
        capability="image_gen",
    )
    return search_space


async def _default_unset_roles(
    session: AsyncSession,
    conn: Connection,
    models: list[Model],
) -> None:
    if conn.scope != ConnectionScope.SEARCH_SPACE or conn.search_space_id is None:
        return
    search_space = await _get_search_space(session, conn.search_space_id)
    if search_space.chat_model_id is None:
        search_space.chat_model_id = _default_model_for(models, "chat")
    if search_space.vision_model_id is None:
        vision_default = None
        if search_space.chat_model_id:
            chat_model = next(
                (m for m in models if m.id == search_space.chat_model_id), None
            )
            if chat_model and has_capability(chat_model, "vision"):
                vision_default = chat_model.id
        search_space.vision_model_id = vision_default or _default_model_for(
            models, "vision"
        )
    if search_space.image_gen_model_id is None:
        search_space.image_gen_model_id = _default_model_for(models, "image_gen")


@router.get("/model-providers", response_model=list[ModelProviderRead])
async def list_model_providers(user: User = Depends(current_active_user)):
    del user
    local_only = {"ollama_chat", "lm_studio"}
    return [
        ModelProviderRead(
            provider=provider,
            transport=spec.transport.value,
            discovery=spec.discovery,
            default_base_url=spec.default_base_url,
            base_url_required=spec.base_url_required,
            auth_style=spec.auth_style,
            local_only=provider in local_only,
        )
        for provider, spec in sorted(REGISTRY.items())
    ]


async def _get_search_space(session: AsyncSession, search_space_id: int) -> SearchSpace:
    result = await session.execute(
        select(SearchSpace).where(SearchSpace.id == search_space_id)
    )
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
        raise HTTPException(
            status_code=403, detail="Connection does not belong to user"
        )


@router.get("/global-llm-config-status")
async def global_llm_config_status(user: User = Depends(current_active_user)):
    del user
    return {"exists": config.GLOBAL_LLM_CONFIG_FILE_EXISTS}


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
        _connection_read(conn, list(conn.models)) for conn in result.scalars().all()
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
    payload = data.model_dump(exclude={"search_space_id", "models"})

    conn = Connection(
        **payload,
        search_space_id=data.search_space_id
        if data.scope == ConnectionScope.SEARCH_SPACE
        else None,
        user_id=user.id,
    )
    session.add(conn)
    await session.flush()

    seen_model_ids: set[str] = set()
    for selection in data.models:
        model_id = selection.model_id.strip()
        if not model_id or model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        session.add(_selection_to_model(conn, selection))

    await session.commit()
    conn = await _load_connection(session, conn.id)
    await _default_unset_roles(session, conn, list(conn.models))
    await session.commit()
    conn = await _load_connection(session, conn.id)
    return _connection_read(conn, list(conn.models))


@router.post(
    "/model-connections/discover-preview", response_model=list[ModelPreviewRead]
)
async def preview_connection_models(
    data: ConnectionCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if data.scope == ConnectionScope.SEARCH_SPACE and data.search_space_id is not None:
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this search space",
        )

    draft = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=data.scope,
        enabled=data.enabled,
        search_space_id=data.search_space_id
        if data.scope == ConnectionScope.SEARCH_SPACE
        else None,
        user_id=user.id,
    )
    try:
        discovered = await discover_models(draft)
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_preview_model_read(item) for item in discovered]


@router.post("/model-connections/test-preview", response_model=VerifyConnectionResponse)
async def test_preview_connection_model(
    data: ModelTestPreview,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if data.scope == ConnectionScope.SEARCH_SPACE and data.search_space_id is not None:
        await check_permission(
            session,
            user,
            data.search_space_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this search space",
        )

    model_id = data.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    draft = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=data.scope,
        enabled=data.enabled,
        search_space_id=data.search_space_id
        if data.scope == ConnectionScope.SEARCH_SPACE
        else None,
        user_id=user.id,
    )
    model = Model(
        connection_id=0,
        model_id=model_id,
        source=ModelSource.MANUAL,
        enabled=True,
        capabilities_override={},
        catalog={},
    )
    result = await test_model(draft, model)
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.put("/model-connections/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    connection_id: int,
    data: ConnectionUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_UPDATE.value
    )
    search_space_id = conn.search_space_id
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(conn, key, value)
    await session.commit()
    if search_space_id is not None:
        await _clear_invalid_roles(session, search_space_id)
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
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_DELETE.value
    )
    search_space_id = conn.search_space_id
    await session.delete(conn)
    await session.commit()
    if search_space_id is not None:
        await _clear_invalid_roles(session, search_space_id)
        await session.commit()
    return {"status": "deleted"}


@router.post(
    "/model-connections/{connection_id}/verify", response_model=VerifyConnectionResponse
)
async def verify_model_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_CREATE.value
    )
    result = await verify_connection(conn)
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.post(
    "/model-connections/{connection_id}/discover", response_model=list[ModelRead]
)
async def discover_connection_models(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_CREATE.value
    )
    try:
        discovered = await discover_models(conn)
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    by_model_id = {model.model_id: model for model in conn.models}
    for item in discovered:
        db_model = by_model_id.get(item["model_id"])
        if db_model is None:
            db_model = Model(
                connection_id=conn.id,
                model_id=item["model_id"],
                display_name=item.get("display_name"),
                source=item["source"],
                capabilities_override={},
                enabled=False,
                catalog=item.get("metadata") or {},
            )
            _apply_model_facts(db_model, item)
            session.add(db_model)
        else:
            db_model.display_name = item.get("display_name") or db_model.display_name
            _apply_model_facts(db_model, item)
            db_model.catalog = item.get("metadata") or db_model.catalog
    await session.commit()
    conn = await _load_connection(session, connection_id)
    await _default_unset_roles(session, conn, list(conn.models))
    if conn.search_space_id is not None:
        await _clear_invalid_roles(session, conn.search_space_id)
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
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_UPDATE.value
    )

    model_id = data.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
    if any(existing.model_id == model_id for existing in conn.models):
        raise HTTPException(
            status_code=400, detail="Model already exists on this connection"
        )

    capabilities = derive_capabilities(conn, model_id)
    model = Model(
        connection_id=conn.id,
        model_id=model_id,
        display_name=data.display_name or None,
        source=ModelSource.MANUAL,
        capabilities_override={},
        enabled=True,
        catalog={},
    )
    _apply_model_facts(model, capabilities)
    session.add(model)
    await session.commit()
    await session.refresh(model)
    conn = await _load_connection(session, connection_id)
    await _default_unset_roles(session, conn, list(conn.models))
    if conn.search_space_id is not None:
        await _clear_invalid_roles(session, conn.search_space_id)
    await session.commit()
    await session.refresh(model)
    return _model_read(model)


@router.patch(
    "/model-connections/{connection_id}/models", response_model=list[ModelRead]
)
async def bulk_update_models(
    connection_id: int,
    data: ModelsBulkUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, user, conn, Permission.LLM_CONFIGS_UPDATE.value
    )
    search_space_id = conn.search_space_id

    model_ids = set(data.model_ids)
    await session.execute(
        update(Model)
        .where(Model.connection_id == connection_id, Model.id.in_(model_ids))
        .values(enabled=data.enabled)
    )
    await session.commit()
    session.expire_all()
    if search_space_id is not None:
        await _clear_invalid_roles(session, search_space_id)
        await session.commit()
        session.expire_all()

    result = await session.execute(
        select(Model)
        .where(Model.connection_id == connection_id, Model.id.in_(model_ids))
        .order_by(Model.id)
    )
    return [_model_read(model) for model in result.scalars().all()]


@router.put("/models/{model_id}", response_model=ModelRead)
async def update_model(
    model_id: int,
    data: ModelUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .where(Model.id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await _assert_connection_access(
        session, user, model.connection, Permission.LLM_CONFIGS_UPDATE.value
    )
    search_space_id = model.connection.search_space_id
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(model, key, value)
    await session.commit()
    await session.refresh(model)
    if search_space_id is not None:
        await _clear_invalid_roles(session, search_space_id)
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
        select(Model)
        .options(selectinload(Model.connection))
        .where(Model.id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await _assert_connection_access(
        session, user, model.connection, Permission.LLM_CONFIGS_UPDATE.value
    )
    result = await test_model(model.connection, model)
    await session.commit()
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.get(
    "/search-spaces/{search_space_id}/model-roles", response_model=ModelRolesRead
)
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
    search_space = await _clear_invalid_roles(session, search_space_id)
    await session.commit()
    await session.refresh(search_space)
    return ModelRolesRead(
        chat_model_id=search_space.chat_model_id,
        vision_model_id=search_space.vision_model_id,
        image_gen_model_id=search_space.image_gen_model_id,
    )


@router.put(
    "/search-spaces/{search_space_id}/model-roles", response_model=ModelRolesRead
)
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
    updates = data.model_dump(exclude_unset=True)
    if "chat_model_id" in updates:
        previous_chat_model_id = search_space.chat_model_id
        next_chat_model_id = await _validate_role_model_id(
            session,
            search_space_id=search_space_id,
            model_id=updates["chat_model_id"],
            capability="chat",
        )
        search_space.chat_model_id = next_chat_model_id
        if next_chat_model_id != previous_chat_model_id:
            await session.execute(
                update(NewChatThread)
                .where(NewChatThread.search_space_id == search_space_id)
                .values(pinned_llm_config_id=None)
            )
            logger.info(
                "Cleared auto model pins for search_space_id=%s after chat_model_id change (%s -> %s)",
                search_space_id,
                previous_chat_model_id,
                next_chat_model_id,
            )
    if "vision_model_id" in updates:
        search_space.vision_model_id = await _validate_role_model_id(
            session,
            search_space_id=search_space_id,
            model_id=updates["vision_model_id"],
            capability="vision",
        )
    if "image_gen_model_id" in updates:
        search_space.image_gen_model_id = await _validate_role_model_id(
            session,
            search_space_id=search_space_id,
            model_id=updates["image_gen_model_id"],
            capability="image_gen",
        )
    await session.commit()
    await session.refresh(search_space)
    return ModelRolesRead(
        chat_model_id=search_space.chat_model_id,
        vision_model_id=search_space.vision_model_id,
        image_gen_model_id=search_space.image_gen_model_id,
    )
