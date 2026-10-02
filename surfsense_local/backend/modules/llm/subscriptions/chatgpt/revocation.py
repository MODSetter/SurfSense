"""Ending a ChatGPT grant at OpenAI, not only forgetting it here."""

import logging

import httpx
from sqlalchemy.orm import Session

from modules.egress import service as egress
from modules.egress.service import EgressDeniedError
from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints
from modules.llm.subscriptions.chatgpt.token_set import TokenSet

logger = logging.getLogger(__name__)

REVOKE_TIMEOUT = httpx.Timeout(5.0, connect=2.0)


def may_revoke(session: Session) -> bool:
    """Only while the sign-in host is still allowed: a host the person turned
    off is not called, even to sign out."""
    try:
        egress.require(session, egress.host_destination(get_endpoints().auth_url))
    except EgressDeniedError:
        return False
    return True


def revoke(tokens: TokenSet) -> None:
    """Best effort (RFC 7009): the local sign-out stands whatever OpenAI answers."""
    try:
        httpx.post(
            get_endpoints().revoke_url,
            data={
                "token": tokens.refresh_token,
                "token_type_hint": "refresh_token",
                "client_id": tokens.client_id,
            },
            timeout=REVOKE_TIMEOUT,
        ).raise_for_status()
    except httpx.HTTPError:
        logger.warning("Could not revoke the ChatGPT refresh token", exc_info=True)
