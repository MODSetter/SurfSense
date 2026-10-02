"""A ChatGPT connection's token stays usable across the API and the workers.

Refresh tokens rotate, so two processes refreshing the same one would leave
the slower holding a revoked token. SQLite's write lock lets one refresh while
the other waits and then reads the winner's token.
"""

import asyncio
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine

from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_responses import SignInRequiredError
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from modules.llm.subscriptions.chatgpt.tokens import (
    ConnectionAccess,
    read_tokens,
    write_tokens,
)
from shared.db import create_db_engine, create_session_factory

from .fake_openai import ISSUED_CLIENT, FakeOpenAI

pytestmark = pytest.mark.integration


def _signed_in(engine: Engine, fake: FakeOpenAI, *, expires_in: float) -> int:
    issued = fake.tokens()
    tokens = TokenSet(
        client_id=ISSUED_CLIENT,
        access_token=issued["access_token"],
        refresh_token=issued["refresh_token"],
        id_token=issued["id_token"],
        expires_at=time.time() + expires_in,
        account="user-1",
        email="reader@example.com",
    )
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label="ChatGPT",
            provider="openai_compatible",
            base_url=f"{fake.url}/v1",
            catalog_provider="openai",
            auth_kind="chatgpt",
        )
        write_tokens(connection, tokens)
        session.add(connection)
        session.commit()
        return connection.id


def _stored(engine: Engine, connection_id: int) -> TokenSet | None:
    with create_session_factory(engine)() as session:
        return read_tokens(session.get(ProviderConnection, connection_id))


async def test_a_fresh_token_is_used_without_asking_openai(
    engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """Most calls touch no network for the token."""
    connection_id = _signed_in(engine, fake_openai, expires_in=3600)

    token = await ConnectionAccess(engine, connection_id)(False)

    assert token == "at-1"
    assert fake_openai.refreshes == 0


async def test_a_token_near_expiry_is_refreshed_and_the_new_one_stored(
    engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """Refreshed early, so a long stream does not outlive its token."""
    connection_id = _signed_in(engine, fake_openai, expires_in=60)

    token = await ConnectionAccess(engine, connection_id)(False)

    stored = _stored(engine, connection_id)
    assert token == "at-2" == stored.access_token
    assert stored.refresh_token == "rt-2"
    assert fake_openai.refreshes == 1


async def test_a_refused_token_is_refreshed_even_when_it_looks_fresh(
    engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """The endpoint's 401 outranks the local clock."""
    connection_id = _signed_in(engine, fake_openai, expires_in=3600)
    access = ConnectionAccess(engine, connection_id)
    await access(False)

    token = await access(True)

    assert token == "at-2"


def test_two_processes_refreshing_at_once_ask_openai_once_and_share_the_token(
    tmp_path: Path, engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """A rotated refresh token used twice would sign the account out."""
    connection_id = _signed_in(engine, fake_openai, expires_in=60)
    fake_openai.refresh_delay = 0.5
    path = Path(engine.url.database)
    tokens: list[str] = []

    def process() -> None:
        # Its own engine, as the API and a worker each open their own.
        own = create_db_engine(path)
        tokens.append(asyncio.run(ConnectionAccess(own, connection_id)(False)))

    threads = [threading.Thread(target=process) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert tokens == ["at-2", "at-2"]
    assert fake_openai.refreshes == 1


async def test_a_dead_refresh_token_signs_the_connection_out(
    engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """invalid_grant cannot heal, so the tokens are cleared, not retried."""
    connection_id = _signed_in(engine, fake_openai, expires_in=60)
    fake_openai.revoked_refresh.add("rt-1")

    with pytest.raises(SignInRequiredError):
        await ConnectionAccess(engine, connection_id)(False)

    assert _stored(engine, connection_id) is None


async def test_a_signed_out_connection_asks_to_sign_in(
    engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """No tokens is the Reconnect state, not an error to retry."""
    connection_id = _signed_in(engine, fake_openai, expires_in=3600)
    with create_session_factory(engine)() as session:
        write_tokens(session.get(ProviderConnection, connection_id), None)
        session.commit()

    with pytest.raises(SignInRequiredError):
        await ConnectionAccess(engine, connection_id)(False)
