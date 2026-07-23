from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.config import config
from app.db import PersonalAccessToken, get_async_session
from app.observability import analytics as ph_analytics
from app.schemas.pat import PATCreate, PATCreated, PATRead
from app.users import require_session_context
from app.utils.pat import generate_pat, hash_pat, token_prefix

router = APIRouter()


def _expires_at(expires_in_days: int | None) -> datetime | None:
    max_expiry_days = config.PAT_MAX_EXPIRY_DAYS

    if max_expiry_days is not None:
        if expires_in_days is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This deployment requires PATs to have an expiry of "
                    f"{max_expiry_days} days or less"
                ),
            )
        if expires_in_days > max_expiry_days:
            raise HTTPException(
                status_code=400,
                detail=f"PAT expiry cannot exceed {max_expiry_days} days",
            )

    if expires_in_days is None:
        return None

    return datetime.now(UTC) + timedelta(days=expires_in_days)


@router.post("/pats", response_model=PATCreated)
async def create_personal_access_token(
    body: PATCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> PATCreated:
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=auth.user.id,
        token_hash=hash_pat(token),
        token_prefix=token_prefix(token),
        label=body.label.strip(),
        expires_at=_expires_at(body.expires_in_days),
    )
    session.add(pat)
    await session.commit()
    await session.refresh(pat)

    # Leading indicator of MCP / programmatic-API adoption.
    ph_analytics.capture_for(
        auth,
        "pat_created",
        {"pat_id": pat.id, "has_expiry": pat.expires_at is not None},
    )

    return PATCreated(
        id=pat.id,
        label=pat.label,
        token=token,
        prefix=pat.token_prefix,
        expires_at=pat.expires_at,
    )


@router.get("/pats", response_model=list[PATRead])
async def list_personal_access_tokens(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> list[PATRead]:
    result = await session.execute(
        select(PersonalAccessToken)
        .where(PersonalAccessToken.user_id == auth.user.id)
        .order_by(PersonalAccessToken.created_at.desc())
    )
    return [
        PATRead(
            id=pat.id,
            label=pat.label,
            prefix=pat.token_prefix,
            expires_at=pat.expires_at,
            last_used_at=pat.last_used_at,
            created_at=pat.created_at,
        )
        for pat in result.scalars().all()
    ]


@router.delete("/pats/{pat_id}", status_code=204)
async def delete_personal_access_token(
    pat_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> None:
    await session.execute(
        delete(PersonalAccessToken).where(
            PersonalAccessToken.id == pat_id,
            PersonalAccessToken.user_id == auth.user.id,
        )
    )
    await session.commit()

    ph_analytics.capture_for(auth, "pat_revoked", {"pat_id": pat_id})
