"""Download and trial routes for offline desktop licenses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeError

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    LicensePurchase,
    LicenseTrialClaim,
    get_async_session,
)
from app.services.license_service import fulfill_license_session, issue_license
from app.signup_credit.identity.registry import identities_of
from app.users import UserManager, get_auth_context, get_user_manager

from .stripe_routes import get_stripe_client

router = APIRouter(prefix="/license", tags=["license"])


async def _optional_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
) -> AuthContext | None:
    try:
        return await get_auth_context(request, session, user_manager)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def _license_file(purchase: LicensePurchase) -> Response:
    return Response(
        content=purchase.certificate,
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="surfsense.lic"',
        },
    )


@router.get("/file")
async def download_license(
    session_id: str | None = None,
    auth: AuthContext | None = Depends(_optional_auth_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Download by opaque Stripe session id or by the signed-in user's email."""
    purchase: LicensePurchase | None
    if session_id:
        purchase = (
            await db_session.execute(
                select(LicensePurchase).where(
                    LicensePurchase.stripe_checkout_session_id == session_id
                )
            )
        ).scalar_one_or_none()

        if purchase is None and config.STRIPE_SECRET_KEY:
            try:
                checkout_session = get_stripe_client().v1.checkout.sessions.retrieve(
                    session_id
                )
                purchase = await fulfill_license_session(
                    db_session,
                    checkout_session,
                )
            except (StripeError, ValueError):
                purchase = None
    else:
        if auth is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        if not auth.is_session:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires an interactive session",
            )
        purchase = (
            await db_session.execute(
                select(LicensePurchase)
                .where(func.lower(LicensePurchase.email) == auth.user.email.lower())
                .order_by(LicensePurchase.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if purchase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found.",
        )
    return _license_file(purchase)


@router.post("/trial")
async def claim_trial_license(
    auth: AuthContext | None = Depends(_optional_auth_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Issue one dark-launched trial per email and stable login identity."""
    if not config.LICENSE_TRIAL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License trial is not available.",
        )
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    if not auth.is_session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an interactive session",
        )

    user = auth.user
    email = user.email.strip().lower()
    await db_session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"license-trial:{email}"},
    )
    existing = (
        await db_session.execute(
            select(LicensePurchase.id).where(
                LicensePurchase.source == "trial",
                func.lower(LicensePurchase.email) == email,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A trial license has already been claimed.",
        )

    identities = identities_of(user)
    if identities:
        claimed = await db_session.execute(
            postgres_insert(LicenseTrialClaim)
            .values(
                [
                    {
                        "identity_kind": identity.kind,
                        "identity_fingerprint": identity.fingerprint,
                    }
                    for identity in identities
                ]
            )
            .on_conflict_do_nothing(
                index_elements=["identity_kind", "identity_fingerprint"]
            )
            .returning(LicenseTrialClaim.id)
        )
        if len(claimed.scalars().all()) != len(identities):
            await db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A trial license has already been claimed.",
            )

    purchase = await issue_license(
        db_session,
        plan="trial",
        email=email,
        source="trial",
    )
    await db_session.commit()
    return _license_file(purchase)
