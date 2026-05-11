"""Test-only token mint endpoint for the E2E backend entrypoint.

Mounted by ``tests/e2e/run_backend.py`` so Playwright can authenticate
the seeded e2e user without hitting ``/auth/jwt/login`` (rate-limited
to 5/min/IP in production). NEVER ships to production: this whole
``tests/`` tree is excluded from the production Docker image by
``surfsense_backend/.dockerignore``.

Authn: shared secret in ``X-E2E-Mint-Secret``. Same value is set on the
backend container env (``docker/docker-compose.e2e.yml``) and exported
to the Playwright runner (``.github/workflows/e2e-tests.yml``).
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db import User, async_session_maker
from app.users import get_jwt_strategy

_logger = logging.getLogger("surfsense.e2e.auth_mint")


class MintRequest(BaseModel):
    email: str = "e2e-test@surfsense.net"


class MintResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _expected_secret() -> str:
    return os.environ.get("E2E_MINT_SECRET", "local-e2e-mint-secret-not-for-production")


router = APIRouter(prefix="/__e2e__", tags=["__e2e__"])


@router.post("/auth/token", response_model=MintResponse)
async def mint_test_token(
    body: MintRequest,
    x_e2e_mint_secret: str = Header(..., alias="X-E2E-Mint-Secret"),
) -> MintResponse:
    if x_e2e_mint_secret != _expected_secret():
        raise HTTPException(status_code=403, detail="invalid e2e mint secret")
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404, detail=f"e2e user {body.email!r} not seeded"
        )
    token = await get_jwt_strategy().write_token(user)
    return MintResponse(access_token=token)


def install(app: FastAPI) -> None:
    """Mount the test-only mint router onto the given FastAPI app."""
    app.include_router(router)
    _logger.warning("[e2e] mounted POST /__e2e__/auth/token (test-only token mint)")
