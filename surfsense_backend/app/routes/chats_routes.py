from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    Chat,
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import (
    AISDKChatRequest,
    ChatCreate,
    ChatRead,
    ChatReadWithoutMessages,
    ChatUpdate,
    NewChatRequest,
)
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.stream_connector_search_results import (
    stream_connector_search_results,
)
from app.tasks.chat.stream_new_chat import stream_new_chat
from app.users import current_active_user
from app.utils.rbac import check_permission
from app.utils.validators import (
    validate_connectors,
    validate_document_ids,
    validate_messages,
    validate_research_mode,
    validate_search_space_id,
    validate_top_k,
)

router = APIRouter()


@router.post("/chat")
async def handle_chat_data(
    request: AISDKChatRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    # Validate and sanitize all input data
    messages = validate_messages(request.messages)

    if messages[-1]["role"] != "user":
        raise HTTPException(
            status_code=400, detail="Last message must be a user message"
        )

    user_query = messages[-1]["content"]

    # Extract and validate data from request
    request_data = request.data or {}
    search_space_id = validate_search_space_id(request_data.get("search_space_id"))
    research_mode = validate_research_mode(request_data.get("research_mode"))
    selected_connectors = validate_connectors(request_data.get("selected_connectors"))
    document_ids_to_add_in_context = validate_document_ids(
        request_data.get("document_ids_to_add_in_context")
    )
    top_k = validate_top_k(request_data.get("top_k"))
    # print("RESQUEST DATA:", request_data)
    # print("SELECTED CONNECTORS:", selected_connectors)

    # Check if the user has chat access to the search space
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to use chat in this search space",
        )

        # Get search space with LLM configs (preferences are now stored at search space level)
        search_space_result = await session.execute(
            select(SearchSpace)
            .options(selectinload(SearchSpace.llm_configs))
            .filter(SearchSpace.id == search_space_id)
        )
        search_space = search_space_result.scalars().first()

        language = None
        llm_configs = []  # Initialize to empty list

        if search_space and search_space.llm_configs:
            llm_configs = search_space.llm_configs

            # Get language from configured LLM preferences
            # LLM preferences are now stored on the SearchSpace model
            from app.config import config as app_config

            for llm_id in [
                search_space.fast_llm_id,
                search_space.long_context_llm_id,
                search_space.strategic_llm_id,
            ]:
                if llm_id is not None:
                    # Check if it's a global config (negative ID)
                    if llm_id < 0:
                        # Look in global configs
                        for global_cfg in app_config.GLOBAL_LLM_CONFIGS:
                            if global_cfg.get("id") == llm_id:
                                language = global_cfg.get("language")
                                if language:
                                    break
                    else:
                        # Look in custom configs
                        for llm_config in llm_configs:
                            if llm_config.id == llm_id and getattr(
                                llm_config, "language", None
                            ):
                                language = llm_config.language
                                break
                    if language:
                        break

        if not language and llm_configs:
            first_llm_config = llm_configs[0]
            language = getattr(first_llm_config, "language", None)

    except HTTPException:
        raise HTTPException(
            status_code=403, detail="You don't have access to this search space"
        ) from None

    langchain_chat_history = []
    for message in messages[:-1]:
        if message["role"] == "user":
            langchain_chat_history.append(HumanMessage(content=message["content"]))
        elif message["role"] == "assistant":
            langchain_chat_history.append(AIMessage(content=message["content"]))

    response = StreamingResponse(
        stream_connector_search_results(
            user_query,
            user.id,
            search_space_id,
            session,
            research_mode,
            selected_connectors,
            langchain_chat_history,
            document_ids_to_add_in_context,
            language,
            top_k,
        )
    )

    response.headers["x-vercel-ai-data-stream"] = "v1"
    return response


@router.post("/new_chat")
async def handle_new_chat(
    request: NewChatRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Handle new chat requests using the SurfSense deep agent.

    This endpoint uses the new deep agent with the Vercel AI SDK
    Data Stream Protocol (SSE format).

    Args:
        request: NewChatRequest containing chat_id, user_query, and search_space_id
        session: Database session
        user: Current authenticated user

    Returns:
        StreamingResponse with SSE formatted data
    """
    # Validate the user query
    if not request.user_query or not request.user_query.strip():
        raise HTTPException(status_code=400, detail="User query cannot be empty")

    # Check if the user has chat access to the search space
    try:
        await check_permission(
            session,
            user,
            request.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to use chat in this search space",
        )
    except HTTPException:
        raise HTTPException(
            status_code=403, detail="You don't have access to this search space"
        ) from None

    # Get LLM config ID from search space preferences (optional enhancement)
    # For now, we use the default global config (-1)
    llm_config_id = -1

    # Optionally load LLM preferences from search space
    try:
        search_space_result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == request.search_space_id)
        )
        search_space = search_space_result.scalars().first()

        if search_space:
            # Use strategic_llm_id if available, otherwise fall back to fast_llm_id
            if search_space.strategic_llm_id is not None:
                llm_config_id = search_space.strategic_llm_id
            elif search_space.fast_llm_id is not None:
                llm_config_id = search_space.fast_llm_id
    except Exception:
        # Fall back to default config on any error
        pass

    # Create the streaming response
    # chat_id is used as LangGraph's thread_id for automatic chat history management
    response = StreamingResponse(
        stream_new_chat(
            user_query=request.user_query.strip(),
            user_id=user.id,
            search_space_id=request.search_space_id,
            chat_id=request.chat_id,
            session=session,
            llm_config_id=llm_config_id,
        ),
        media_type="text/event-stream",
    )

    # Set the required headers for Vercel AI SDK
    headers = VercelStreamingService.get_response_headers()
    for key, value in headers.items():
        response.headers[key] = value

    return response


@router.post("/chats", response_model=ChatRead)
async def create_chat(
    chat: ChatCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new chat.
    Requires CHATS_CREATE permission.
    """
    try:
        await check_permission(
            session,
            user,
            chat.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to create chats in this search space",
        )
        db_chat = Chat(**chat.model_dump())
        session.add(db_chat)
        await session.commit()
        await session.refresh(db_chat)
        return db_chat
    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while creating the chat.",
        ) from None


@router.get("/chats", response_model=list[ChatReadWithoutMessages])
async def read_chats(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List chats the user has access to.
    Requires CHATS_READ permission for the search space(s).
    """
    # Validate pagination parameters
    if skip < 0:
        raise HTTPException(
            status_code=400, detail="skip must be a non-negative integer"
        )

    if limit <= 0 or limit > 1000:  # Reasonable upper limit
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    # Validate search_space_id if provided
    if search_space_id is not None and search_space_id <= 0:
        raise HTTPException(
            status_code=400, detail="search_space_id must be a positive integer"
        )
    try:
        if search_space_id is not None:
            # Check permission for specific search space
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.CHATS_READ.value,
                "You don't have permission to read chats in this search space",
            )
            # Select specific fields excluding messages
            query = select(
                Chat.id,
                Chat.type,
                Chat.title,
                Chat.initial_connectors,
                Chat.search_space_id,
                Chat.created_at,
                Chat.state_version,
            ).filter(Chat.search_space_id == search_space_id)
        else:
            # Get chats from all search spaces user has membership in
            query = (
                select(
                    Chat.id,
                    Chat.type,
                    Chat.title,
                    Chat.initial_connectors,
                    Chat.search_space_id,
                    Chat.created_at,
                    Chat.state_version,
                )
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
            )

        result = await session.execute(query.offset(skip).limit(limit))
        return result.all()
    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while fetching chats."
        ) from None


@router.get("/chats/{chat_id}", response_model=ChatRead)
async def read_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific chat by ID.
    Requires CHATS_READ permission for the search space.
    """
    try:
        result = await session.execute(select(Chat).filter(Chat.id == chat_id))
        chat = result.scalars().first()

        if not chat:
            raise HTTPException(
                status_code=404,
                detail="Chat not found",
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            chat.search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        return chat
    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching the chat.",
        ) from None


@router.put("/chats/{chat_id}", response_model=ChatRead)
async def update_chat(
    chat_id: int,
    chat_update: ChatUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a chat.
    Requires CHATS_UPDATE permission for the search space.
    """
    try:
        result = await session.execute(select(Chat).filter(Chat.id == chat_id))
        db_chat = result.scalars().first()

        if not db_chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Check permission for the search space
        await check_permission(
            session,
            user,
            db_chat.search_space_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this search space",
        )

        update_data = chat_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "messages":
                db_chat.state_version = len(update_data["messages"])
            setattr(db_chat, key, value)

        await session.commit()
        await session.refresh(db_chat)
        return db_chat
    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the chat.",
        ) from None


@router.delete("/chats/{chat_id}", response_model=dict)
async def delete_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a chat.
    Requires CHATS_DELETE permission for the search space.
    """
    try:
        result = await session.execute(select(Chat).filter(Chat.id == chat_id))
        db_chat = result.scalars().first()

        if not db_chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Check permission for the search space
        await check_permission(
            session,
            user,
            db_chat.search_space_id,
            Permission.CHATS_DELETE.value,
            "You don't have permission to delete chats in this search space",
        )

        await session.delete(db_chat)
        await session.commit()
        return {"message": "Chat deleted successfully"}
    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete chat due to existing dependencies."
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while deleting the chat.",
        ) from None
