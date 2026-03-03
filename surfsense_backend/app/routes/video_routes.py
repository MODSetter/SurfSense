"""Video file serving route.

The video pipeline is triggered by the chat agent's generate_video tool.
This route only serves the rendered MP4 files.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.agents.video.constants import LOCAL_VIDEO_STORAGE_DIR

router = APIRouter()


@router.get("/video/files/{thread_id}/{filename}")
async def serve_video_file(thread_id: str, filename: str):
    """Serve a rendered MP4 file."""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = LOCAL_VIDEO_STORAGE_DIR / thread_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
    )
