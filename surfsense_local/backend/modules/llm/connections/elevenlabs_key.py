import asyncio

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress import service as egress
from modules.llm.providers.elevenlabs.account import (
    ElevenLabsRefusedError,
    verify_key,
)


async def require_usable_key(session: Session, base_url: str, api_key: str) -> None:
    """Refuse a key with ElevenLabs' own sentence, which names a missing permission."""
    await transact(session, egress.require, egress.host_destination(base_url))
    try:
        await asyncio.to_thread(verify_key, base_url, api_key)
    except ElevenLabsRefusedError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "elevenlabs_refused", "message": str(error)},
        ) from error
