import asyncio
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from modules.llm.subscriptions.chatgpt import account
from modules.llm.subscriptions.chatgpt.endpoints import (
    AGENT_NAME,
    DYNAMIC_CLIENT,
    PLAN_SCOPE,
    RESOURCE,
    SCOPE,
    get_endpoints,
)
from modules.llm.subscriptions.chatgpt.host_id import host_id
from modules.llm.subscriptions.chatgpt.id_token import (
    InvalidIdTokenError,
    verified_claims,
)
from modules.llm.subscriptions.chatgpt.loopback import Loopback
from modules.llm.subscriptions.chatgpt.pkce import Pkce
from modules.llm.subscriptions.chatgpt.token_endpoint import (
    TokenRefusedError,
    exchange_code,
)
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from modules.llm.subscriptions.chatgpt.tokens import read_tokens
from shared.secrets import UnreadableSecretError

# Long enough to sign in and approve in a browser, short enough that an
# abandoned flow does not hold a port.
SIGN_IN_SECONDS = 300

FlowStatus = Literal["waiting", "signed_in", "failed"]
SessionFactory = Callable[[], Session]


class _SignInFailedError(Exception):
    pass


@dataclass
class Flow:
    id: str
    authorize_url: str
    status: FlowStatus = "waiting"
    connection_id: int | None = None
    message: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


class SignInFlows:
    """Sign-ins in progress, held in the API's memory: only the API signs in."""

    def __init__(self) -> None:
        self._flows: dict[str, Flow] = {}

    def get(self, flow_id: str) -> Flow | None:
        return self._flows.get(flow_id)

    def cancel(self, flow_id: str) -> None:
        flow = self._flows.pop(flow_id, None)
        if flow is not None and flow.task is not None:
            flow.task.cancel()

    async def start(
        self,
        session_factory: SessionFactory,
        *,
        label: str | None,
        connection_id: int | None,
    ) -> Flow:
        self._forget_settled()
        returning = (
            await asyncio.to_thread(_returning, session_factory, connection_id)
            if connection_id is not None
            else None
        )
        pkce = Pkce()
        loopback = Loopback()
        redirect_uri = await loopback.open()
        flow = Flow(
            secrets.token_urlsafe(16), _authorize_url(pkce, redirect_uri, returning)
        )
        self._flows[flow.id] = flow
        flow.task = asyncio.create_task(
            self._finish(
                flow,
                loopback,
                pkce,
                redirect_uri,
                session_factory,
                label,
                connection_id,
                returning,
            )
        )
        return flow

    def _forget_settled(self) -> None:
        for flow_id in [k for k, f in self._flows.items() if f.status != "waiting"]:
            del self._flows[flow_id]

    async def _finish(
        self,
        flow: Flow,
        loopback: Loopback,
        pkce: Pkce,
        redirect_uri: str,
        session_factory: SessionFactory,
        label: str | None,
        connection_id: int | None,
        returning: TokenSet | None,
    ) -> None:
        try:
            async with asyncio.timeout(SIGN_IN_SECONDS):
                query = await loopback.callback()
            tokens = await _tokens(query, pkce, redirect_uri, returning)
            flow.connection_id = await asyncio.to_thread(
                _save, session_factory, tokens, label, connection_id
            )
            flow.status = "signed_in"
        except TimeoutError:
            _fail(flow, "The sign-in was not finished in time.")
        except (
            _SignInFailedError,
            account.LabelTakenError,
            account.NotChatGPTError,
            InvalidIdTokenError,
            TokenRefusedError,
        ) as error:
            _fail(flow, str(error))
        except (httpx.HTTPError, ValueError, KeyError):
            _fail(flow, "OpenAI could not be reached to finish the sign-in.")
        finally:
            loopback.close()


def _returning(session_factory: SessionFactory, connection_id: int) -> TokenSet | None:
    """The sign-in a connection still holds, which OpenAI's returning-user path reuses."""
    with session_factory() as session:
        connection = account.chatgpt_connection(session, connection_id)
        try:
            return read_tokens(connection)
        except UnreadableSecretError:
            # Tokens this install can no longer read: register afresh.
            return None


def _authorize_url(pkce: Pkce, redirect_uri: str, returning: TokenSet | None) -> str:
    query = {
        "client_id": returning.client_id if returning else DYNAMIC_CLIENT,
        "agent_name_hint": AGENT_NAME,
        "ext_agent_host_id": host_id(),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
        "resource": RESOURCE,
        "state": pkce.state,
        "nonce": pkce.nonce,
        "code_challenge_method": "S256",
        "code_challenge": pkce.challenge,
    }
    if returning:
        query["id_token_hint"] = returning.id_token
    return f"{get_endpoints().authorize_url}?{urlencode(query)}"


async def _tokens(
    query: dict[str, str], pkce: Pkce, redirect_uri: str, returning: TokenSet | None
) -> TokenSet:
    if query.get("state") != pkce.state:
        raise _SignInFailedError("The sign-in answered a different request.")
    if "error" in query:
        raise _SignInFailedError(
            query.get("error_description") or "The sign-in was declined."
        )
    client_id, code = query.get("client_id"), query.get("code")
    if not client_id or not code:
        raise _SignInFailedError("OpenAI's answer carried no sign-in code.")
    if returning and client_id != returning.client_id:
        # OpenAI's guide: never let a renewal switch the connection's registration.
        raise _SignInFailedError("OpenAI answered for a different registration.")
    reply = await exchange_code(client_id, code, pkce.verifier, redirect_uri)
    if PLAN_SCOPE not in str(reply.get("scope", "")).split():
        raise _SignInFailedError("ChatGPT plan usage was not allowed for SurfSense.")
    if not reply.get("refresh_token") or not reply.get("id_token"):
        raise _SignInFailedError("OpenAI's answer was missing a token.")
    claims = await verified_claims(reply["id_token"], client_id, pkce.nonce)
    now = time.time()
    return TokenSet(
        client_id=client_id,
        access_token=reply["access_token"],
        refresh_token=reply["refresh_token"],
        id_token=reply["id_token"],
        expires_at=now + float(reply.get("expires_in") or 3600),
        account=claims["sub"],
        email=claims.get("email"),
    ).refreshed(reply, now)


def _save(
    session_factory: SessionFactory,
    tokens: TokenSet,
    label: str | None,
    connection_id: int | None,
) -> int:
    with session_factory() as session:
        saved = account.save_sign_in(
            session, tokens, label=label, connection_id=connection_id
        )
        session.commit()
        return saved


def _fail(flow: Flow, message: str) -> None:
    flow.status = "failed"
    flow.message = message
