"""Signed infographic style selection and generation-sidecar state."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.sandbox import SandboxSession

from .presets import get_visual_style
from .schemas import ResolvedVisualStyle

SELECTION_TOKEN_TTL_SECONDS = 60 * 60
SIDECAR_PREFIX = "/tmp/.surfsense-infographic-generation-"


class InfographicSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    workspace_id: int
    thread_id: int
    preset_id: str
    preset_version: int = Field(ge=1)
    requested_style_id: str
    resolved_style_id: str
    issued_at: int


class InfographicGenerationState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    workspace_id: int
    session_id: str
    output_path: str
    selection_digest: str
    attempts: int = Field(ge=1, le=2)
    png_sha256: str
    markdown_sha256: str
    requested_style_id: str
    resolved_style_id: str
    preset_id: str
    preset_version: int
    image_gen_model_id: int
    provider_model: str | None = Field(default=None, max_length=300)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    issued_at: int

    def manifest_provenance(self) -> dict[str, Any]:
        return {
            "question_preset_id": self.preset_id,
            "question_preset_version": self.preset_version,
            "requested_style_id": self.requested_style_id,
            "resolved_style_id": self.resolved_style_id,
            "image_gen_model_id": self.image_gen_model_id,
            "provider_model": self.provider_model,
            "width": self.width,
            "height": self.height,
        }


def _payload(value: BaseModel | dict[str, Any]) -> bytes:
    data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _sign(payload: bytes, secret_key: str) -> str:
    if not secret_key:
        raise ValueError("SECRET_KEY is required for infographic generation")
    return hmac.new(secret_key.encode(), payload, hashlib.sha256).hexdigest()


def issue_selection_token(
    *,
    workspace_id: int,
    thread_id: int,
    preset_id: str,
    preset_version: int,
    resolved: ResolvedVisualStyle,
    secret_key: str,
    now: int | None = None,
) -> str:
    selection = InfographicSelection(
        workspace_id=workspace_id,
        thread_id=thread_id,
        preset_id=preset_id,
        preset_version=preset_version,
        requested_style_id=resolved.requested_id,
        resolved_style_id=resolved.resolved_id,
        issued_at=int(time.time()) if now is None else now,
    )
    payload = _payload(selection)
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{encoded}.{_sign(payload, secret_key)}"


def read_selection_token(
    token: str,
    *,
    workspace_id: int,
    thread_id: int,
    secret_key: str,
    now: int | None = None,
) -> InfographicSelection:
    try:
        encoded, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if not hmac.compare_digest(signature, _sign(payload, secret_key)):
            raise ValueError
        selection = InfographicSelection.model_validate_json(payload)
    except Exception:
        raise ValueError("Infographic selection token is invalid") from None
    if selection.workspace_id != workspace_id or selection.thread_id != thread_id:
        raise ValueError("Infographic selection belongs to another workspace or thread")
    age = (int(time.time()) if now is None else now) - selection.issued_at
    if age < 0 or age > SELECTION_TOKEN_TTL_SECONDS:
        raise ValueError("Infographic selection token has expired")
    preset = get_visual_style(selection.resolved_style_id)
    if preset.version != selection.preset_version:
        raise ValueError("Infographic selection references an unavailable preset")
    return selection


def selection_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generation_sidecar_path(output_path: str) -> str:
    path = PurePosixPath(output_path)
    if not path.is_absolute() or not path.name:
        raise ValueError("Infographic output path must be an absolute file path")
    return f"{SIDECAR_PREFIX}{hashlib.sha256(output_path.encode()).hexdigest()}.json"


async def write_generation_state(
    session: SandboxSession,
    state: InfographicGenerationState,
    *,
    secret_key: str,
) -> None:
    payload = state.model_dump(mode="json")
    envelope = {"payload": payload, "signature": _sign(_payload(payload), secret_key)}
    await session.write_file(
        generation_sidecar_path(state.output_path),
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(),
    )


async def read_generation_state(
    session: SandboxSession,
    output_path: str,
    *,
    workspace_id: int,
    secret_key: str,
) -> InfographicGenerationState | None:
    try:
        raw = await session.read_file(generation_sidecar_path(output_path))
    except (FileNotFoundError, KeyError):
        return None
    try:
        envelope = json.loads(raw.decode())
        payload = envelope["payload"]
        signature = envelope["signature"]
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError
        if not hmac.compare_digest(signature, _sign(_payload(payload), secret_key)):
            raise ValueError
        state = InfographicGenerationState.model_validate(payload)
    except Exception:
        raise ValueError("Infographic generation metadata is invalid") from None
    if state.workspace_id != workspace_id or state.session_id != session.session_id:
        raise ValueError("Infographic generation metadata belongs to another workspace")
    if state.output_path != output_path:
        raise ValueError("Infographic generation metadata targets another file")
    return state


__all__ = [
    "InfographicGenerationState",
    "InfographicSelection",
    "generation_sidecar_path",
    "issue_selection_token",
    "read_generation_state",
    "read_selection_token",
    "selection_digest",
    "write_generation_state",
]
