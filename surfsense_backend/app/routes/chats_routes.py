from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain.schema import AIMessage, HumanMessage
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import Chat, SearchSpace, User, UserSearchSpacePreference, get_async_session
from app.schemas import (
    AISDKChatRequest,
    ChatCreate,
    ChatRead,
    ChatReadWithoutMessages,
    ChatUpdate,
)
from app.tasks.stream_connector_search_results import stream_connector_search_results
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from app.utils.validators import (
    validate_connectors,
    validate_document_ids,
    validate_messages,
    validate_research_mode,
    validate_search_mode,
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
    search_mode_str = validate_search_mode(request_data.get("search_mode"))
    top_k = validate_top_k(request_data.get("top_k"))
    # print("RESQUEST DATA:", request_data)
    # print("SELECTED CONNECTORS:", selected_connectors)

    # Check if the search space belongs to the current user
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)
        language_result = await session.execute(
            select(UserSearchSpacePreference)
            .options(
                selectinload(UserSearchSpacePreference.search_space).selectinload(
                    SearchSpace.llm_configs
                ),
                selectinload(UserSearchSpacePreference.long_context_llm),
                selectinload(UserSearchSpacePreference.fast_llm),
                selectinload(UserSearchSpacePreference.strategic_llm),
            )
            .filter(
                UserSearchSpacePreference.search_space_id == search_space_id,
                UserSearchSpacePreference.user_id == user.id,
            )
        )
        user_preference = language_result.scalars().first()
        # print("UserSearchSpacePreference:", user_preference)

        language = None
        if (
            user_preference
            and user_preference.search_space
            and user_preference.search_space.llm_configs
        ):
            llm_configs = user_preference.search_space.llm_configs

            for preferred_llm in [
                user_preference.fast_llm,
                user_preference.long_context_llm,
                user_preference.strategic_llm,
            ]:
                if preferred_llm and getattr(preferred_llm, "language", None):
                    language = preferred_llm.language
                    break

        if not language:
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
            search_mode_str,
            document_ids_to_add_in_context,
            language,
            top_k,
        )
    )

    response.headers["x-vercel-ai-data-stream"] = "v1"
    return response


@router.post("/chats", response_model=ChatRead)
async def create_chat(
    chat: ChatCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_ownership(session, SearchSpace, chat.search_space_id, user)
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
        # Select specific fields excluding messages
        query = (
            select(
                Chat.id,
                Chat.type,
                Chat.title,
                Chat.initial_connectors,
                Chat.search_space_id,
                Chat.created_at,
            )
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
        )

        # Filter by search_space_id if provided
        if search_space_id is not None:
            query = query.filter(Chat.search_space_id == search_space_id)

        result = await session.execute(query.offset(skip).limit(limit))
        return result.all()
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
    try:
        result = await session.execute(
            select(Chat)
            .join(SearchSpace)
            .filter(Chat.id == chat_id, SearchSpace.user_id == user.id)
        )
        chat = result.scalars().first()
        if not chat:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to access it",
            )
        return chat
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
    try:
        db_chat = await read_chat(chat_id, session, user)
        update_data = chat_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
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
    try:
        db_chat = await read_chat(chat_id, session, user)
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
