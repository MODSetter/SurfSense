import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    Connection,
    ConnectionScope,
    Model,
    ModelSource,
    NewChatThread,
    Permission,
    Workspace,
    get_async_session,
    has_permission,
)
from app.schemas import (
    ConnectionCreate,
    ConnectionRead,
    ConnectionUpdate,
    LlmSetupStatusRead,
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
from app.users import get_auth_context, require_session_context
from app.utils.rbac import check_permission, get_user_permissions

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
        workspace_id=conn.workspace_id,
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
    workspace_id: int,
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
    if model is None or model.connection.workspace_id != workspace_id:
        return None
    return model


def _role_model_enabled(model: Model | dict) -> bool:
    if isinstance(model, dict):
        return bool(model.get("enabled", True))
    return bool(model.enabled and model.connection.enabled)


async def _validate_role_model_id(
    session: AsyncSession,
    *,
    workspace_id: int,
    model_id: int | None,
    capability: str,
) -> int:
    if model_id is None or model_id == 0:
        return 0

    model = await _load_role_model(session, workspace_id, model_id)
    if model and _role_model_enabled(model) and has_capability(model, capability):
        return model_id

    raise HTTPException(
        status_code=400,
        detail=f"Selected model is not available for {capability}",
    )


async def _resolve_role_model_id(
    session: AsyncSession,
    *,
    workspace_id: int,
    model_id: int | None,
    capability: str,
) -> int:
    try:
        return await _validate_role_model_id(
            session,
            workspace_id=workspace_id,
            model_id=model_id,
            capability=capability,
        )
    except HTTPException:
        return 0


async def _clear_invalid_roles(session: AsyncSession, workspace_id: int) -> Workspace:
    workspace = await _get_workspace(session, workspace_id)
    workspace.chat_model_id = await _resolve_role_model_id(
        session,
        workspace_id=workspace_id,
        model_id=workspace.chat_model_id,
        capability="chat",
    )
    workspace.vision_model_id = await _resolve_role_model_id(
        session,
        workspace_id=workspace_id,
        model_id=workspace.vision_model_id,
        capability="vision",
    )
    workspace.image_gen_model_id = await _resolve_role_model_id(
        session,
        workspace_id=workspace_id,
        model_id=workspace.image_gen_model_id,
        capability="image_gen",
    )
    return workspace


async def _default_unset_roles(
    session: AsyncSession,
    conn: Connection,
    models: list[Model],
) -> None:
    if conn.scope != ConnectionScope.SEARCH_SPACE or conn.workspace_id is None:
        return
    workspace = await _get_workspace(session, conn.workspace_id)
    if workspace.chat_model_id is None:
        workspace.chat_model_id = _default_model_for(models, "chat")
    if workspace.vision_model_id is None:
        vision_default = None
        if workspace.chat_model_id:
            chat_model = next(
                (m for m in models if m.id == workspace.chat_model_id), None
            )
            if chat_model and has_capability(chat_model, "vision"):
                vision_default = chat_model.id
        workspace.vision_model_id = vision_default or _default_model_for(
            models, "vision"
        )
    if workspace.image_gen_model_id is None:
        workspace.image_gen_model_id = _default_model_for(models, "image_gen")


@router.get("/model-providers", response_model=list[ModelProviderRead])
async def list_model_providers(auth: AuthContext = Depends(require_session_context)):
    del auth
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


async def _get_workspace(session: AsyncSession, workspace_id: int) -> Workspace:
    result = await session.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


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
    auth: AuthContext,
    conn: Connection,
    permission: str = Permission.LLM_CONFIGS_CREATE.value,
    allow_spaceless_pat: bool = False,
) -> None:
    user = auth.user
    if conn.workspace_id:
        await check_permission(
            session,
            auth,
            conn.workspace_id,
            permission,
            "You don't have permission to manage model connections in this workspace",
        )
        return
    if conn.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Connection does not belong to user"
        )
    if auth.is_gated and not allow_spaceless_pat:
        raise HTTPException(
            status_code=403,
            detail="Managing personal model connections requires an interactive session",
        )


@router.get("/global-llm-config-status")
async def global_llm_config_status(
    auth: AuthContext = Depends(require_session_context),
):
    del auth
    return {"exists": config.GLOBAL_LLM_CONFIG_FILE_EXISTS}


@router.get("/global-model-connections", response_model=list[ConnectionRead])
async def list_global_connections(auth: AuthContext = Depends(require_session_context)):
    del auth
    models_by_connection: dict[int, list[dict]] = {}
    for model in config.GLOBAL_MODELS:
        models_by_connection.setdefault(model["connection_id"], []).append(model)
    return [
        _connection_read(conn, models_by_connection.get(conn["id"], []))
        for conn in config.GLOBAL_CONNECTIONS
    ]


@router.get("/model-connections", response_model=list[ConnectionRead])
async def list_connections(
    workspace_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    stmt = select(Connection).options(selectinload(Connection.models))
    if workspace_id is not None:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.LLM_CONFIGS_READ.value,
            "You don't have permission to view model connections in this workspace",
        )
        stmt = stmt.where(Connection.workspace_id == workspace_id)
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
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    if data.scope == ConnectionScope.GLOBAL:
        raise HTTPException(status_code=400, detail="GLOBAL connections are YAML-only")
    if data.scope == ConnectionScope.SEARCH_SPACE:
        if data.workspace_id is None:
            raise HTTPException(status_code=400, detail="workspace_id is required")
        await check_permission(
            session,
            auth,
            data.workspace_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this workspace",
        )
    elif auth.is_gated:
        raise HTTPException(
            status_code=403,
            detail="Managing personal model connections requires an interactive session",
        )
    payload = data.model_dump(exclude={"workspace_id", "models"})

    conn = Connection(
        **payload,
        workspace_id=data.workspace_id
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
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    if data.scope == ConnectionScope.SEARCH_SPACE and data.workspace_id is not None:
        await check_permission(
            session,
            auth,
            data.workspace_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this workspace",
        )
    elif auth.is_gated:
        raise HTTPException(
            status_code=403,
            detail="Testing personal model connections requires an interactive session",
        )

    draft = Connection(
        provider=data.provider,
        base_url=data.base_url,
        api_key=data.api_key,
        extra=data.extra or {},
        scope=data.scope,
        enabled=data.enabled,
        workspace_id=data.workspace_id
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
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    if data.scope == ConnectionScope.SEARCH_SPACE and data.workspace_id is not None:
        await check_permission(
            session,
            auth,
            data.workspace_id,
            Permission.LLM_CONFIGS_CREATE.value,
            "You don't have permission to create model connections in this workspace",
        )
    elif auth.is_gated:
        raise HTTPException(
            status_code=403,
            detail="Testing personal model connections requires an interactive session",
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
        workspace_id=data.workspace_id
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
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_UPDATE.value
    )
    workspace_id = conn.workspace_id
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(conn, key, value)
    await session.commit()
    if workspace_id is not None:
        await _clear_invalid_roles(session, workspace_id)
        await session.commit()
    conn = await _load_connection(session, connection_id)
    return _connection_read(conn, list(conn.models))


@router.delete("/model-connections/{connection_id}")
async def delete_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_DELETE.value
    )
    workspace_id = conn.workspace_id
    await session.delete(conn)
    await session.commit()
    if workspace_id is not None:
        await _clear_invalid_roles(session, workspace_id)
        await session.commit()
    return {"status": "deleted"}


@router.post(
    "/model-connections/{connection_id}/verify", response_model=VerifyConnectionResponse
)
async def verify_model_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_CREATE.value
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
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_CREATE.value
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
    if conn.workspace_id is not None:
        await _clear_invalid_roles(session, conn.workspace_id)
    await session.commit()
    conn = await _load_connection(session, connection_id)
    return [_model_read(model) for model in conn.models]


@router.post("/model-connections/{connection_id}/models", response_model=ModelRead)
async def add_manual_model(
    connection_id: int,
    data: ModelCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_UPDATE.value
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
    if conn.workspace_id is not None:
        await _clear_invalid_roles(session, conn.workspace_id)
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
    auth: AuthContext = Depends(get_auth_context),
):
    conn = await _load_connection(session, connection_id)
    await _assert_connection_access(
        session, auth, conn, Permission.LLM_CONFIGS_UPDATE.value
    )
    workspace_id = conn.workspace_id

    model_ids = set(data.model_ids)
    await session.execute(
        update(Model)
        .where(Model.connection_id == connection_id, Model.id.in_(model_ids))
        .values(enabled=data.enabled)
    )
    await session.commit()
    session.expire_all()
    if workspace_id is not None:
        await _clear_invalid_roles(session, workspace_id)
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
    auth: AuthContext = Depends(get_auth_context),
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
        session, auth, model.connection, Permission.LLM_CONFIGS_UPDATE.value
    )
    workspace_id = model.connection.workspace_id
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(model, key, value)
    await session.commit()
    await session.refresh(model)
    if workspace_id is not None:
        await _clear_invalid_roles(session, workspace_id)
        await session.commit()
        await session.refresh(model)
    return _model_read(model)


@router.post("/models/{model_id}/test", response_model=VerifyConnectionResponse)
async def test_connection_model(
    model_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
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
        session, auth, model.connection, Permission.LLM_CONFIGS_UPDATE.value
    )
    result = await test_model(model.connection, model)
    await session.commit()
    return VerifyConnectionResponse(
        status=result.status, ok=result.ok, message=result.message
    )


@router.get("/workspaces/{workspace_id}/model-roles", response_model=ModelRolesRead)
async def get_model_roles(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LLM_CONFIGS_READ.value,
        "You don't have permission to view model roles in this workspace",
    )
    workspace = await _clear_invalid_roles(session, workspace_id)
    await session.commit()
    await session.refresh(workspace)
    return ModelRolesRead(
        chat_model_id=workspace.chat_model_id,
        vision_model_id=workspace.vision_model_id,
        image_gen_model_id=workspace.image_gen_model_id,
    )


@router.put("/workspaces/{workspace_id}/model-roles", response_model=ModelRolesRead)
async def update_model_roles(
    workspace_id: int,
    data: ModelRolesUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LLM_CONFIGS_UPDATE.value,
        "You don't have permission to update model roles in this workspace",
    )
    workspace = await _get_workspace(session, workspace_id)
    updates = data.model_dump(exclude_unset=True)
    if "chat_model_id" in updates:
        previous_chat_model_id = workspace.chat_model_id
        next_chat_model_id = await _validate_role_model_id(
            session,
            workspace_id=workspace_id,
            model_id=updates["chat_model_id"],
            capability="chat",
        )
        workspace.chat_model_id = next_chat_model_id
        if next_chat_model_id != previous_chat_model_id:
            await session.execute(
                update(NewChatThread)
                .where(NewChatThread.workspace_id == workspace_id)
                .values(pinned_llm_config_id=None)
            )
            logger.info(
                "Cleared auto model pins for workspace_id=%s after chat_model_id change (%s -> %s)",
                workspace_id,
                previous_chat_model_id,
                next_chat_model_id,
            )
    if "vision_model_id" in updates:
        workspace.vision_model_id = await _validate_role_model_id(
            session,
            workspace_id=workspace_id,
            model_id=updates["vision_model_id"],
            capability="vision",
        )
    if "image_gen_model_id" in updates:
        workspace.image_gen_model_id = await _validate_role_model_id(
            session,
            workspace_id=workspace_id,
            model_id=updates["image_gen_model_id"],
            capability="image_gen",
        )
    await session.commit()
    await session.refresh(workspace)
    return ModelRolesRead(
        chat_model_id=workspace.chat_model_id,
        vision_model_id=workspace.vision_model_id,
        image_gen_model_id=workspace.image_gen_model_id,
    )


def _global_catalog_has_usable_chat() -> bool:
    """True when the operator global catalog exposes a usable chat model.

    Checks usability (enabled connection + enabled, chat-capable model), not
    mere presence of ``global_llm_config.yaml`` — an empty or malformed file,
    or an OpenRouter-only config whose startup fetch failed, yields no models
    and must fall through to onboarding.
    """
    enabled_connection_ids = {
        conn["id"] for conn in config.GLOBAL_CONNECTIONS if conn.get("enabled", True)
    }
    return any(
        model.get("connection_id") in enabled_connection_ids
        and model.get("enabled", True)
        and has_capability(model, "chat")
        for model in config.GLOBAL_MODELS
    )


async def _workspace_has_enabled_chat_model(
    session: AsyncSession, workspace_id: int
) -> bool:
    result = await session.execute(
        select(Connection)
        .options(selectinload(Connection.models))
        .where(
            Connection.workspace_id == workspace_id,
            Connection.enabled,
        )
    )
    return any(
        model.enabled and has_capability(model, "chat")
        for conn in result.scalars().all()
        for model in conn.models
    )


async def compute_llm_setup_status(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> LlmSetupStatusRead:
    """Single source of truth for whether a workspace can chat.

    "Needs onboarding" is derived, never persisted: a workspace is ``ready``
    exactly when a usable chat model resolves for it (operator global catalog,
    a valid pinned role, or an enabled chat-capable model in Auto mode).
    """
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LLM_CONFIGS_READ.value,
        "You don't have permission to view LLM setup status in this workspace",
    )
    permissions = await get_user_permissions(session, auth.user.id, workspace_id)
    can_configure = has_permission(permissions, Permission.LLM_CONFIGS_CREATE.value)

    global_usable = _global_catalog_has_usable_chat()
    if config.GLOBAL_LLM_CONFIG_FILE_EXISTS and global_usable:
        # Global readiness is never stamped: it is not this workspace's own setup.
        return LlmSetupStatusRead(
            status="ready",
            source="global_config",
            can_configure=can_configure,
            stage="ready",
        )

    # Heal dangling role pins first: a chat_model_id pointing at a deleted or
    # disabled model collapses to 0 (Auto) here, so the checks below see the
    # real state.
    workspace = await _clear_invalid_roles(session, workspace_id)
    await session.commit()
    await session.refresh(workspace)

    async def _stamp_own_setup() -> None:
        # Record first own-model readiness once; the guard makes concurrent
        # stamps idempotent. (Writing on this GET is precedented above.)
        if workspace.llm_setup_completed_at is None:
            workspace.llm_setup_completed_at = datetime.now(UTC)
            await session.commit()

    chat_model_id = workspace.chat_model_id or 0
    if chat_model_id != 0:
        # Survived _clear_invalid_roles => valid, enabled, chat-capable.
        source = "global_config" if chat_model_id < 0 else "models"
        if source == "models":
            await _stamp_own_setup()
        return LlmSetupStatusRead(
            status="ready", source=source, can_configure=can_configure, stage="ready"
        )

    if global_usable:
        return LlmSetupStatusRead(
            status="ready",
            source="global_config",
            can_configure=can_configure,
            stage="ready",
        )
    if await _workspace_has_enabled_chat_model(session, workspace_id):
        await _stamp_own_setup()
        return LlmSetupStatusRead(
            status="ready", source="models", can_configure=can_configure, stage="ready"
        )

    # A set timestamp => self-configured before (recovery); NULL => never (first-run).
    stage = "recovery" if workspace.llm_setup_completed_at else "initial_setup"
    return LlmSetupStatusRead(
        status="needs_setup", source="none", can_configure=can_configure, stage=stage
    )


@router.get(
    "/workspaces/{workspace_id}/llm-setup-status",
    response_model=LlmSetupStatusRead,
)
async def llm_setup_status(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await compute_llm_setup_status(session, auth, workspace_id)
