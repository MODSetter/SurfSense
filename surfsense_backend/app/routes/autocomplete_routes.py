from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.services.new_streaming_service import VercelStreamingService
from app.services.vision_autocomplete_service import stream_vision_autocomplete
from app.users import current_active_user

router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


class VisionAutocompleteRequest(BaseModel):
    screenshot: str
    search_space_id: int
    app_name: str = ""
    window_title: str = ""


@router.post("/vision/stream")
async def vision_autocomplete_stream(
    body: VisionAutocompleteRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return StreamingResponse(
        stream_vision_autocomplete(
            body.screenshot, body.search_space_id, session,
            app_name=body.app_name, window_title=body.window_title,
        ),
        media_type="text/event-stream",
        headers={
            **VercelStreamingService.get_response_headers(),
            "X-Accel-Buffering": "no",
        },
    )
