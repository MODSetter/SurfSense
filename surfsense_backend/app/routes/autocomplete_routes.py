from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.services.autocomplete_service import stream_autocomplete
from app.services.new_streaming_service import VercelStreamingService
from app.users import current_active_user

router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


@router.post("/stream")
async def autocomplete_stream(
    text: str = Query(..., description="Current text in the input field"),
    cursor_position: int = Query(-1, description="Cursor position in the text (-1 for end)"),
    search_space_id: int = Query(..., description="Search space ID for KB context and LLM config"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if cursor_position < 0:
        cursor_position = len(text)

    return StreamingResponse(
        stream_autocomplete(text, cursor_position, search_space_id, session),
        media_type="text/event-stream",
        headers={
            **VercelStreamingService.get_response_headers(),
            "X-Accel-Buffering": "no",
        },
    )
