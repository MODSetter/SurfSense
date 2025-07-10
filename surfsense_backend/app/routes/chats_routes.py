from typing import List

from app.db import Chat, SearchSpace, User, get_async_session
from app.schemas import AISDKChatRequest, ChatCreate, ChatRead, ChatUpdate
from app.tasks.stream_connector_search_results import stream_connector_search_results
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langchain.schema import HumanMessage, AIMessage


router = APIRouter()

@router.post("/chat")
async def handle_chat_data(
    request: AISDKChatRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    messages = request.messages
    if messages[-1]['role'] != "user":
        raise HTTPException(
            status_code=400, detail="Last message must be a user message")

    user_query = messages[-1]['content']
    search_space_id = request.data.get('search_space_id')
    research_mode: str = request.data.get('research_mode')
    selected_connectors: List[str] = request.data.get('selected_connectors')
    document_ids_to_add_in_context: List[int] = request.data.get('document_ids_to_add_in_context')
    
    search_mode_str = request.data.get('search_mode', "CHUNKS")

    # Convert search_space_id to integer if it's a string
    if search_space_id and isinstance(search_space_id, str):
        try:
            search_space_id = int(search_space_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid search_space_id format")

    # Check if the search space belongs to the current user
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)
    except HTTPException:
        raise HTTPException(
            status_code=403, detail="You don't have access to this search space")
        
    langchain_chat_history = []
    for message in messages[:-1]:
        if message['role'] == "user":
            langchain_chat_history.append(HumanMessage(content=message['content']))
        elif message['role'] == "assistant":
            # Find the last "ANSWER" annotation specifically
            answer_annotation = None
            for annotation in reversed(message['annotations']):
                if annotation['type'] == "ANSWER":
                    answer_annotation = annotation
                    break
            
            if answer_annotation:
                answer_text = answer_annotation['content']
                # If content is a list, join it into a single string
                if isinstance(answer_text, list):
                    answer_text = "\n".join(answer_text)
                langchain_chat_history.append(AIMessage(content=answer_text))

    response = StreamingResponse(stream_connector_search_results(
        user_query,
        user.id,
        search_space_id,  # Already converted to int in lines 32-37
        session,
        research_mode,
        selected_connectors,
        langchain_chat_history,
        search_mode_str,
        document_ids_to_add_in_context
    ))
    response.headers['x-vercel-ai-data-stream'] = 'v1'
    return response


@router.post("/chats/", response_model=ChatRead)
async def create_chat(
    chat: ChatCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail="Database constraint violation. Please check your input data.")
    except OperationalError as e:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later.")
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while creating the chat.")


@router.get("/chats/", response_model=List[ChatRead])
async def read_chats(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        query = select(Chat).join(SearchSpace).filter(SearchSpace.user_id == user.id)
        
        # Filter by search_space_id if provided
        if search_space_id is not None:
            query = query.filter(Chat.search_space_id == search_space_id)
            
        result = await session.execute(
            query.offset(skip).limit(limit)
        )
        return result.scalars().all()
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later.")
    except Exception:
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while fetching chats.")


@router.get("/chats/{chat_id}", response_model=ChatRead)
async def read_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
                status_code=404, detail="Chat not found or you don't have permission to access it")
        return chat
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later.")
    except Exception:
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while fetching the chat.")


@router.put("/chats/{chat_id}", response_model=ChatRead)
async def update_chat(
    chat_id: int,
    chat_update: ChatUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
            status_code=400, detail="Database constraint violation. Please check your input data.")
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later.")
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while updating the chat.")


@router.delete("/chats/{chat_id}", response_model=dict)
async def delete_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
            status_code=400, detail="Cannot delete chat due to existing dependencies.")
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later.")
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while deleting the chat.")


# test_data = [
#     {
#         "type": "TERMINAL_INFO",
#         "content": [
#             {
#                 "id": 1,
#                 "text": "Starting to search for crawled URLs...",
#                 "type": "info"
#             },
#             {
#                 "id": 2,
#                 "text": "Found 2 relevant crawled URLs",
#                 "type": "success"
#             }
#         ]
#     },
#     {
#         "type": "SOURCES",
#         "content": [
#             {
#                 "id": 1,
#                 "name": "Crawled URLs",
#                 "type": "CRAWLED_URL",
#                 "sources": [
#                     {
#                         "id": 1,
#                         "title": "Webpage Title",
#                         "description": "Webpage Dec",
#                         "url": "https://jsoneditoronline.org/"
#                     },
#                     {
#                         "id": 2,
#                         "title": "Webpage Title",
#                         "description": "Webpage Dec",
#                         "url": "https://www.google.com/"
#                     }
#                 ]
#             },
#             {
#                 "id": 2,
#                 "name": "Files",
#                 "type": "FILE",
#                 "sources": [
#                     {
#                         "id": 3,
#                         "title": "Webpage Title",
#                         "description": "Webpage Dec",
#                         "url": "https://jsoneditoronline.org/"
#                     },
#                     {
#                         "id": 4,
#                         "title": "Webpage Title",
#                         "description": "Webpage Dec",
#                         "url": "https://www.google.com/"
#                     }
#                 ]
#             }
#         ]
#     },
#     {
#         "type": "ANSWER",
#         "content": [
#             "## SurfSense Introduction",
#             "Surfsense is A Personal NotebookLM and Perplexity-like AI Assistant for Everyone. Research and Never forget Anything. [1] [3]"
#         ]
#     }
# ]
