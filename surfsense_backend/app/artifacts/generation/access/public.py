"""The anonymous SEO-funnel door: one POST per public generator + a catalog.

No login, no workspace, no persistence — build an anonymous context, run the
generic pipeline, return the bytes. Abuse is capped like anonymous chat
(Turnstile past a per-IP threshold + a hard per-IP daily cap) and the whole
door is gated behind ``NOLOGIN_MODE_ENABLED``. Iterates the same registry the
authenticated doors read.
"""

import contextlib
import logging

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.artifacts.generation.core.context import AnonymousContext, generate
from app.artifacts.generation.core.registry import (
    ArtifactGenerator,
    public_generators,
)
from app.artifacts.generation.core.result import GeneratedBytes
from app.config import config
from app.observability import analytics as ph_analytics
from app.routes.anonymous_chat_routes import (
    _get_client_ip,
    _get_or_create_session_id,
)

logger = logging.getLogger(__name__)


class PublicToolResponse(BaseModel):
    kind: str
    title: str
    description: str
    seo_slug: str


def _require_nologin() -> None:
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )


def build_public_artifact_router() -> APIRouter:
    """Catalog + one bytes-returning POST per public generator."""
    router = APIRouter(prefix="/api/v1/public/tools", tags=["public-tools"])

    async def list_public_tools() -> list[PublicToolResponse]:
        _require_nologin()
        return [
            PublicToolResponse(
                kind=gen.kind,
                title=gen.seo.title,
                description=gen.seo.description,
                seo_slug=gen.seo.seo_slug,
            )
            for gen in public_generators()
        ]

    router.add_api_route(
        "", list_public_tools, methods=["GET"],
        response_model=list[PublicToolResponse], name="public_tools:list",
    )

    for gen in public_generators():
        _register(router, gen)

    return router


def _register(router: APIRouter, gen: ArtifactGenerator) -> None:
    input_model = gen.input_schema

    async def endpoint(
        payload: input_model,
        request: Request,
        response: Response,
        x_turnstile_token: str | None = Header(default=None),
    ):
        _require_nologin()

        from app.services.token_quota_service import TokenQuotaService
        from app.services.turnstile_service import verify_turnstile_token

        client_ip = _get_client_ip(request)
        session_id = _get_or_create_session_id(request, response)

        if config.TURNSTILE_ENABLED:
            req_count = await TokenQuotaService.anon_get_request_count(client_ip)
            if req_count >= config.ANON_CAPTCHA_REQUEST_THRESHOLD:
                if not x_turnstile_token:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "CAPTCHA_REQUIRED",
                            "message": "Please complete the CAPTCHA to continue.",
                        },
                    )
                if not await verify_turnstile_token(x_turnstile_token, client_ip):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "CAPTCHA_INVALID",
                            "message": "CAPTCHA verification failed. Please try again.",
                        },
                    )
                await TokenQuotaService.anon_reset_request_count(client_ip)

        # ponytail: one hard per-IP daily cap for the funnel; image is the only
        # public kind today, so its cap knob is reused. Add a per-kind cap when
        # a second public generator lands.
        used = await TokenQuotaService.anon_get_image_count(client_ip)
        if used >= config.ANON_IMAGE_DAILY_CAP_PER_IP:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "ANON_IMAGE_CAP_REACHED",
                    "message": (
                        "You've used all your free generations today. "
                        "Create an account for more."
                    ),
                    "limit": config.ANON_IMAGE_DAILY_CAP_PER_IP,
                },
            )

        ctx = AnonymousContext()
        try:
            result = await generate(gen, ctx, payload)
        except gen.user_facing_errors as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except Exception:
            logger.exception("anonymous %s generation failed", gen.kind)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation failed. Please try again.",
            ) from None

        assert isinstance(result, GeneratedBytes)

        await TokenQuotaService.anon_increment_image_count(client_ip)
        if config.TURNSTILE_ENABLED:
            await TokenQuotaService.anon_increment_request_count(client_ip)

        with contextlib.suppress(Exception):
            if ph_analytics.is_enabled():
                ph_analytics.capture(
                    f"anon_{gen.kind}_generated",
                    distinct_id=session_id,
                    properties={"client": "anonymous", "mime_type": result.mime_type},
                )

        return Response(content=result.data, media_type=result.mime_type)

    # Abuse control is Turnstile + the per-IP daily cap below, plus the app-wide
    # default limiter; no extra per-route slowapi wrapper (it hides the typed
    # body from FastAPI).
    router.add_api_route(
        f"/{gen.kind}", endpoint, methods=["POST"], name=f"public_tools:{gen.kind}"
    )
