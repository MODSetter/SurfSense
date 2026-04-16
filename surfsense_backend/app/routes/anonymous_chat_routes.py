"""Public API endpoints for anonymous (no-login) chat."""

from __future__ import annotations

import logging
import secrets
import uuid
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import config
from app.etl_pipeline.file_classifier import (
    DIRECT_CONVERT_EXTENSIONS,
    PLAINTEXT_EXTENSIONS,
)
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public/anon-chat", tags=["anonymous-chat"])

ANON_COOKIE_NAME = "surfsense_anon_session"
ANON_COOKIE_MAX_AGE = config.ANON_TOKEN_QUOTA_TTL_DAYS * 86400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_session_id(request: Request, response: Response) -> str:
    """Read the signed session cookie or create a new one."""
    session_id = request.cookies.get(ANON_COOKIE_NAME)
    if session_id and len(session_id) == 43:
        return session_id
    session_id = secrets.token_urlsafe(32)
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=session_id,
        max_age=ANON_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return session_id


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AnonChatRequest(BaseModel):
    model_slug: str = Field(..., max_length=100)
    messages: list[dict[str, Any]] = Field(..., min_length=1)
    disabled_tools: list[str] | None = None
    turnstile_token: str | None = None


class AnonQuotaResponse(BaseModel):
    used: int
    limit: int
    remaining: int
    status: str
    warning_threshold: int
    captcha_required: bool = False


class AnonModelResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    provider: str
    model_name: str
    billing_tier: str = "free"
    is_premium: bool = False
    seo_slug: str | None = None
    seo_enabled: bool = False
    seo_title: str | None = None
    seo_description: str | None = None
    quota_reserve_tokens: int | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/models", response_model=list[AnonModelResponse])
async def list_anonymous_models():
    """Return all models enabled for anonymous access."""
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    models = []
    for cfg in config.GLOBAL_LLM_CONFIGS:
        if cfg.get("anonymous_enabled", False):
            models.append(
                AnonModelResponse(
                    id=cfg.get("id", 0),
                    name=cfg.get("name", ""),
                    description=cfg.get("description"),
                    provider=cfg.get("provider", ""),
                    model_name=cfg.get("model_name", ""),
                    billing_tier=cfg.get("billing_tier", "free"),
                    is_premium=cfg.get("billing_tier", "free") == "premium",
                    seo_slug=cfg.get("seo_slug"),
                    seo_enabled=cfg.get("seo_enabled", False),
                    seo_title=cfg.get("seo_title"),
                    seo_description=cfg.get("seo_description"),
                    quota_reserve_tokens=cfg.get("quota_reserve_tokens"),
                )
            )
    return models


@router.get("/models/{slug}", response_model=AnonModelResponse)
async def get_anonymous_model(slug: str):
    """Return a single model by its SEO slug."""
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    for cfg in config.GLOBAL_LLM_CONFIGS:
        if cfg.get("anonymous_enabled", False) and cfg.get("seo_slug") == slug:
            return AnonModelResponse(
                id=cfg.get("id", 0),
                name=cfg.get("name", ""),
                description=cfg.get("description"),
                provider=cfg.get("provider", ""),
                model_name=cfg.get("model_name", ""),
                billing_tier=cfg.get("billing_tier", "free"),
                is_premium=cfg.get("billing_tier", "free") == "premium",
                seo_slug=cfg.get("seo_slug"),
                seo_enabled=cfg.get("seo_enabled", False),
                seo_title=cfg.get("seo_title"),
                seo_description=cfg.get("seo_description"),
                quota_reserve_tokens=cfg.get("quota_reserve_tokens"),
            )

    raise HTTPException(status_code=404, detail="Model not found")


@router.get("/quota", response_model=AnonQuotaResponse)
@limiter.limit("30/minute")
async def get_anonymous_quota(request: Request, response: Response):
    """Return current token usage for the anonymous session.

    Reports the *stricter* of session and IP buckets so that opening a
    new browser on the same IP doesn't show a misleadingly fresh quota.
    """
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    from app.services.token_quota_service import (
        TokenQuotaService,
        compute_anon_identity_key,
        compute_ip_quota_key,
    )

    client_ip = _get_client_ip(request)

    session_id = _get_or_create_session_id(request, response)
    session_key = compute_anon_identity_key(session_id)
    session_result = await TokenQuotaService.anon_get_usage(session_key)

    ip_key = compute_ip_quota_key(client_ip)
    ip_result = await TokenQuotaService.anon_get_usage(ip_key)

    # Use whichever bucket has higher usage — that's the real constraint
    result = ip_result if ip_result.used > session_result.used else session_result

    captcha_needed = False
    if config.TURNSTILE_ENABLED:
        req_count = await TokenQuotaService.anon_get_request_count(client_ip)
        captcha_needed = req_count >= config.ANON_CAPTCHA_REQUEST_THRESHOLD

    return AnonQuotaResponse(
        used=result.used,
        limit=result.limit,
        remaining=result.remaining,
        status=result.status.value,
        warning_threshold=config.ANON_TOKEN_WARNING_THRESHOLD,
        captcha_required=captcha_needed,
    )


@router.post("/stream")
@limiter.limit("15/minute")
async def stream_anonymous_chat(
    body: AnonChatRequest,
    request: Request,
    response: Response,
):
    """Stream a chat response for an anonymous user with quota enforcement."""
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    from app.agents.new_chat.llm_config import (
        AgentConfig,
        create_chat_litellm_from_agent_config,
    )
    from app.services.token_quota_service import (
        TokenQuotaService,
        compute_anon_identity_key,
        compute_ip_quota_key,
    )
    from app.services.turnstile_service import verify_turnstile_token

    # Find the model config by slug
    model_cfg = None
    for cfg in config.GLOBAL_LLM_CONFIGS:
        if (
            cfg.get("anonymous_enabled", False)
            and cfg.get("seo_slug") == body.model_slug
        ):
            model_cfg = cfg
            break

    if model_cfg is None:
        raise HTTPException(
            status_code=404, detail="Model not found or not available for anonymous use"
        )

    client_ip = _get_client_ip(request)

    # --- Concurrent stream limit ---
    slot_acquired = await TokenQuotaService.anon_acquire_stream_slot(
        client_ip, max_concurrent=config.ANON_MAX_CONCURRENT_STREAMS
    )
    if not slot_acquired:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "ANON_TOO_MANY_STREAMS",
                "message": f"Max {config.ANON_MAX_CONCURRENT_STREAMS} concurrent chats allowed. Please wait for a response to finish.",
            },
        )

    try:
        # --- CAPTCHA enforcement (check count without incrementing; count
        #     is bumped only after a successful response in _generate) ---
        if config.TURNSTILE_ENABLED:
            req_count = await TokenQuotaService.anon_get_request_count(client_ip)
            if req_count >= config.ANON_CAPTCHA_REQUEST_THRESHOLD:
                if not body.turnstile_token:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "CAPTCHA_REQUIRED",
                            "message": "Please complete the CAPTCHA to continue chatting.",
                        },
                    )
                valid = await verify_turnstile_token(body.turnstile_token, client_ip)
                if not valid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "CAPTCHA_INVALID",
                            "message": "CAPTCHA verification failed. Please try again.",
                        },
                    )
                await TokenQuotaService.anon_reset_request_count(client_ip)

        # Build identity keys
        session_id = _get_or_create_session_id(request, response)
        session_key = compute_anon_identity_key(session_id)
        ip_key = compute_ip_quota_key(client_ip)

        # Reserve tokens
        reserve_amount = min(
            model_cfg.get("quota_reserve_tokens", config.QUOTA_MAX_RESERVE_PER_CALL),
            config.QUOTA_MAX_RESERVE_PER_CALL,
        )
        request_id = uuid.uuid4().hex[:16]

        quota_result = await TokenQuotaService.anon_reserve(
            session_key=session_key,
            ip_key=ip_key,
            request_id=request_id,
            reserve_tokens=reserve_amount,
        )

        if not quota_result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "ANON_QUOTA_EXCEEDED",
                    "message": "You've used all your free tokens. Create an account for 5M more!",
                    "used": quota_result.used,
                    "limit": quota_result.limit,
                },
            )

        # Create agent config from YAML
        agent_config = AgentConfig.from_yaml_config(model_cfg)
        llm = create_chat_litellm_from_agent_config(agent_config)
        if not llm:
            await TokenQuotaService.anon_release(session_key, ip_key, request_id)
            raise HTTPException(status_code=500, detail="Failed to create LLM instance")

        # Server-side tool allow-list enforcement
        anon_allowed_tools = {"web_search"}
        client_disabled = set(body.disabled_tools) if body.disabled_tools else set()
        enabled_for_agent = anon_allowed_tools - client_disabled

    except HTTPException:
        await TokenQuotaService.anon_release_stream_slot(client_ip)
        raise

    async def _generate():
        from langchain_core.messages import HumanMessage

        from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
        from app.agents.new_chat.checkpointer import get_checkpointer
        from app.db import shielded_async_session
        from app.services.connector_service import ConnectorService
        from app.services.new_streaming_service import VercelStreamingService
        from app.services.token_tracking_service import start_turn
        from app.tasks.chat.stream_new_chat import StreamResult, _stream_agent_events

        accumulator = start_turn()
        streaming_service = VercelStreamingService()

        try:
            async with shielded_async_session() as session:
                connector_service = ConnectorService(session, search_space_id=None)
                checkpointer = await get_checkpointer()

                anon_thread_id = f"anon-{session_id}-{request_id}"

                agent = await create_surfsense_deep_agent(
                    llm=llm,
                    search_space_id=0,
                    db_session=session,
                    connector_service=connector_service,
                    checkpointer=checkpointer,
                    user_id=None,
                    thread_id=None,
                    agent_config=agent_config,
                    enabled_tools=list(enabled_for_agent),
                    disabled_tools=None,
                    anon_session_id=session_id,
                )

                user_query = ""
                for msg in reversed(body.messages):
                    if msg.get("role") == "user":
                        user_query = msg.get("content", "")
                        break

                langchain_messages = [HumanMessage(content=user_query)]
                input_state = {
                    "messages": langchain_messages,
                    "search_space_id": 0,
                }

                langgraph_config = {
                    "configurable": {"thread_id": anon_thread_id},
                    "recursion_limit": 40,
                }

                yield streaming_service.format_message_start()
                yield streaming_service.format_start_step()

                initial_step_id = "thinking-1"
                query_preview = user_query[:80] + (
                    "..." if len(user_query) > 80 else ""
                )
                initial_items = [f"Processing: {query_preview}"]

                yield streaming_service.format_thinking_step(
                    step_id=initial_step_id,
                    title="Understanding your request",
                    status="in_progress",
                    items=initial_items,
                )

                stream_result = StreamResult()

                async for sse in _stream_agent_events(
                    agent=agent,
                    config=langgraph_config,
                    input_data=input_state,
                    streaming_service=streaming_service,
                    result=stream_result,
                    step_prefix="thinking",
                    initial_step_id=initial_step_id,
                    initial_step_title="Understanding your request",
                    initial_step_items=initial_items,
                ):
                    yield sse

            # Finalize quota with actual tokens
            actual_tokens = accumulator.grand_total
            finalize_result = await TokenQuotaService.anon_finalize(
                session_key=session_key,
                ip_key=ip_key,
                request_id=request_id,
                actual_tokens=actual_tokens,
            )

            # Count this as 1 completed response for CAPTCHA threshold
            if config.TURNSTILE_ENABLED:
                await TokenQuotaService.anon_increment_request_count(client_ip)

            yield streaming_service.format_data(
                "anon-quota",
                {
                    "used": finalize_result.used,
                    "limit": finalize_result.limit,
                    "remaining": finalize_result.remaining,
                    "status": finalize_result.status.value,
                },
            )

            if accumulator.per_message_summary():
                yield streaming_service.format_data(
                    "token-usage",
                    {
                        "usage": accumulator.per_message_summary(),
                        "prompt_tokens": accumulator.total_prompt_tokens,
                        "completion_tokens": accumulator.total_completion_tokens,
                        "total_tokens": accumulator.grand_total,
                    },
                )

            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()

        except Exception as e:
            logger.exception("Anonymous chat stream error")
            await TokenQuotaService.anon_release(session_key, ip_key, request_id)
            yield streaming_service.format_error(f"Error during chat: {e!s}")
            yield streaming_service.format_done()
        finally:
            await TokenQuotaService.anon_release_stream_slot(client_ip)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Anonymous Document Upload (1-doc limit, plaintext/direct-convert only)
# ---------------------------------------------------------------------------

ANON_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS | DIRECT_CONVERT_EXTENSIONS
ANON_DOC_REDIS_PREFIX = "anon:doc:"


class AnonDocResponse(BaseModel):
    filename: str
    size_bytes: int
    status: str = "uploaded"


@router.post("/upload", response_model=AnonDocResponse)
@limiter.limit("5/minute")
async def upload_anonymous_document(
    file: UploadFile,
    request: Request,
    response: Response,
):
    """Upload a single document for anonymous chat (1-doc limit per session)."""
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    session_id = _get_or_create_session_id(request, response)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = PurePosixPath(file.filename).suffix.lower()
    if ext not in ANON_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "File type not supported for anonymous upload. "
                "Create an account to upload PDFs, Word documents, images, audio, and 20+ more file types. "
                "Allowed extensions: text, code, CSV, HTML files."
            ),
        )

    max_size = config.ANON_MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {config.ANON_MAX_UPLOAD_SIZE_MB} MB.",
        )

    import json as _json

    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    redis_key = f"{ANON_DOC_REDIS_PREFIX}{session_id}"

    try:
        existing = await redis_client.exists(redis_key)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Document limit reached. Create an account to upload more.",
            )

        text_content: str
        if ext in PLAINTEXT_EXTENSIONS:
            text_content = content.decode("utf-8", errors="replace")
        elif ext in DIRECT_CONVERT_EXTENSIONS:
            if ext in {".csv", ".tsv"}:
                text_content = content.decode("utf-8", errors="replace")
            else:
                try:
                    from markdownify import markdownify

                    text_content = markdownify(
                        content.decode("utf-8", errors="replace")
                    )
                except ImportError:
                    text_content = content.decode("utf-8", errors="replace")
        else:
            text_content = content.decode("utf-8", errors="replace")

        doc_data = _json.dumps(
            {
                "filename": file.filename,
                "size_bytes": len(content),
                "content": text_content,
            }
        )

        ttl_seconds = config.ANON_TOKEN_QUOTA_TTL_DAYS * 86400
        await redis_client.set(redis_key, doc_data, ex=ttl_seconds)

    finally:
        await redis_client.aclose()

    return AnonDocResponse(
        filename=file.filename,
        size_bytes=len(content),
    )


@router.get("/document")
async def get_anonymous_document(request: Request, response: Response):
    """Get metadata of the uploaded document for the anonymous session."""
    if not config.NOLOGIN_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No-login mode is not enabled.",
        )

    session_id = _get_or_create_session_id(request, response)

    import json as _json

    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    redis_key = f"{ANON_DOC_REDIS_PREFIX}{session_id}"

    try:
        data = await redis_client.get(redis_key)
        if not data:
            raise HTTPException(status_code=404, detail="No document uploaded")

        doc = _json.loads(data)
        return {
            "filename": doc["filename"],
            "size_bytes": doc["size_bytes"],
        }
    finally:
        await redis_client.aclose()
