"""Speech-to-Text API routes."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.stt_service import stt_service

router = APIRouter(prefix="/stt", tags=["Speech-to-Text"])


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(None, description="Optional language code (e.g., 'en', 'es')"),
):
    """Transcribe uploaded audio file to text."""
    
    # Validate file type
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400, 
            detail="File must be an audio file"
        )
    
    try:
        # Read audio bytes
        audio_bytes = await audio.read()
        
        # Transcribe
        result = stt_service.transcribe_bytes(
            audio_bytes, 
            filename=audio.filename or "audio.wav",
            language=language if language else None
        )
        
        return JSONResponse(content={
            "success": True,
            "transcription": result["text"],
            "metadata": {
                "detected_language": result["language"],
                "language_probability": result["language_probability"],
                "duration_seconds": result["duration"],
                "model_size": stt_service.model_size,
            }
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )


@router.get("/models")
async def get_available_models():
    """Get list of available Whisper models."""
    return JSONResponse(content={
        "models": [
            {"name": "tiny", "size": "~39 MB", "speed": "fastest", "accuracy": "lowest"},
            {"name": "base", "size": "~74 MB", "speed": "fast", "accuracy": "good"},
            {"name": "small", "size": "~244 MB", "speed": "medium", "accuracy": "better"},
            {"name": "medium", "size": "~769 MB", "speed": "slow", "accuracy": "high"},
            {"name": "large-v3", "size": "~1550 MB", "speed": "slowest", "accuracy": "highest"},
        ],
        "current_model": stt_service.model_size,
        "note": "Models are downloaded automatically on first use"
    })


@router.post("/change-model")
async def change_model(model_size: str = Form(...)):
    """Change the active Whisper model."""
    
    valid_models = ["tiny", "base", "small", "medium", "large-v3"]
    if model_size not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model. Choose from: {valid_models}"
        )
    
    try:
        # Create new service instance with different model
        global stt_service
        stt_service = type(stt_service)(model_size=model_size)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Model changed to {model_size}",
            "note": "Model will be downloaded on next transcription if not cached"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change model: {str(e)}"
        )