import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain.schema import AIMessage, HumanMessage
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Chat, SearchSpace, User, get_async_session
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

router = APIRouter()


def validate_search_space_id(search_space_id: Any) -> int:
    """
    Validate and convert search_space_id to integer.
    
    Args:
        search_space_id: The search space ID to validate
        
    Returns:
        int: Validated search space ID
        
    Raises:
        HTTPException: If validation fails
    """
    if search_space_id is None:
        raise HTTPException(
            status_code=400, 
            detail="search_space_id is required"
        )
    
    if isinstance(search_space_id, int):
        if search_space_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a positive integer"
            )
        return search_space_id
    
    if isinstance(search_space_id, str):
        # Check if it's a valid integer string
        if not search_space_id.strip():
            raise HTTPException(
                status_code=400,
                detail="search_space_id cannot be empty"
            )
        
        # Check for valid integer format (no leading zeros, no decimal points)
        if not re.match(r'^[1-9]\d*$', search_space_id.strip()):
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a valid positive integer"
            )
        
        try:
            value = int(search_space_id.strip())
            if value <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="search_space_id must be a positive integer"
                )
            return value
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a valid integer"
            ) from None
    
    raise HTTPException(
        status_code=400,
        detail="search_space_id must be an integer or string representation of an integer"
    )


def validate_document_ids(document_ids: Any) -> list[int]:
    """
    Validate and convert document_ids to list of integers.
    
    Args:
        document_ids: The document IDs to validate
        
    Returns:
        List[int]: Validated list of document IDs
        
    Raises:
        HTTPException: If validation fails
    """
    if document_ids is None:
        return []
    
    if not isinstance(document_ids, list):
        raise HTTPException(
            status_code=400,
            detail="document_ids_to_add_in_context must be a list"
        )
    
    validated_ids = []
    for i, doc_id in enumerate(document_ids):
        if isinstance(doc_id, int):
            if doc_id <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a positive integer"
                )
            validated_ids.append(doc_id)
        elif isinstance(doc_id, str):
            if not doc_id.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] cannot be empty"
                )
            
            if not re.match(r'^[1-9]\d*$', doc_id.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a valid positive integer"
                )
            
            try:
                value = int(doc_id.strip())
                if value <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"document_ids_to_add_in_context[{i}] must be a positive integer"
                    )
                validated_ids.append(value)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a valid integer"
                ) from None
        else:
            raise HTTPException(
                status_code=400,
                detail=f"document_ids_to_add_in_context[{i}] must be an integer or string representation of an integer"
            )
    
    return validated_ids


def validate_connectors(connectors: Any) -> list[str]:
    """
    Validate selected_connectors list.
    
    Args:
        connectors: The connectors to validate
        
    Returns:
        List[str]: Validated list of connector names
        
    Raises:
        HTTPException: If validation fails
    """
    if connectors is None:
        return []
    
    if not isinstance(connectors, list):
        raise HTTPException(
            status_code=400,
            detail="selected_connectors must be a list"
        )
    
    validated_connectors = []
    for i, connector in enumerate(connectors):
        if not isinstance(connector, str):
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] must be a string"
            )
        
        if not connector.strip():
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] cannot be empty"
            )
        
        # Basic sanitization - remove any potentially dangerous characters
        sanitized = re.sub(r'[^\w\-_]', '', connector.strip())
        if not sanitized:
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] contains invalid characters"
            )
        
        validated_connectors.append(sanitized)
    
    return validated_connectors


def validate_research_mode(research_mode: Any) -> str:
    """
    Validate research_mode parameter.
    
    Args:
        research_mode: The research mode to validate
        
    Returns:
        str: Validated research mode
        
    Raises:
        HTTPException: If validation fails
    """
    if research_mode is None:
        return "GENERAL"  # Default value
    
    if not isinstance(research_mode, str):
        raise HTTPException(
            status_code=400,
            detail="research_mode must be a string"
        )
    
    valid_modes = ["GENERAL", "DEEP", "DEEPER"]
    if research_mode.upper() not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"research_mode must be one of: {', '.join(valid_modes)}"
        )
    
    return research_mode.upper()


def validate_search_mode(search_mode: Any) -> str:
    """
    Validate search_mode parameter.
    
    Args:
        search_mode: The search mode to validate
        
    Returns:
        str: Validated search mode
        
    Raises:
        HTTPException: If validation fails
    """
    if search_mode is None:
        return "CHUNKS"  # Default value
    
    if not isinstance(search_mode, str):
        raise HTTPException(
            status_code=400,
            detail="search_mode must be a string"
        )
    
    valid_modes = ["CHUNKS", "DOCUMENTS"]
    if search_mode.upper() not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"search_mode must be one of: {', '.join(valid_modes)}"
        )
    
    return search_mode.upper()


def validate_messages(messages: Any) -> list[dict]:
    """
    Validate messages structure.
    
    Args:
        messages: The messages to validate
        
    Returns:
        List[dict]: Validated messages
        
    Raises:
        HTTPException: If validation fails
    """
    if not isinstance(messages, list):
        raise HTTPException(
            status_code=400,
            detail="messages must be a list"
        )
    
    if not messages:
        raise HTTPException(
            status_code=400,
            detail="messages cannot be empty"
        )
    
    validated_messages = []
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must be a dictionary"
            )
        
        if "role" not in message:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must have a 'role' field"
            )
        
        if "content" not in message:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must have a 'content' field"
            )
        
        role = message["role"]
        if not isinstance(role, str) or role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].role must be 'user', 'assistant', or 'system'"
            )
        
        content = message["content"]
        if not isinstance(content, str):
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content must be a string"
            )
        
        if not content.strip():
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content cannot be empty"
            )
        
        # Basic content sanitization
        sanitized_content = content.strip()
        if len(sanitized_content) > 10000:  # Reasonable limit
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content is too long (max 10000 characters)"
            )
        
        validated_messages.append({
            "role": role,
            "content": sanitized_content
        })
    
    return validated_messages


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
    document_ids_to_add_in_context = validate_document_ids(request_data.get("document_ids_to_add_in_context"))
    search_mode_str = validate_search_mode(request_data.get("search_mode"))

    # Check if the search space belongs to the current user
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)
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
        )
    )

    response.headers["x-vercel-ai-data-stream"] = "v1"
    return response


@router.post("/chats/", response_model=ChatRead)
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


@router.get("/chats/", response_model=list[ChatReadWithoutMessages])
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
            status_code=400,
            detail="skip must be a non-negative integer"
        )
    
    if limit <= 0 or limit > 1000:  # Reasonable upper limit
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 1000"
        )
    
    # Validate search_space_id if provided
    if search_space_id is not None and search_space_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="search_space_id must be a positive integer"
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
