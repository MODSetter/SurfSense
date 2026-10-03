import asyncio
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, select, update

from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_responses import SignInRequiredError
from modules.llm.subscriptions.chatgpt import token_endpoint
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from shared.secrets import decrypt, encrypt

_TABLE = ProviderConnection.__table__


def read_tokens(connection: ProviderConnection) -> TokenSet | None:
    if connection.oauth_ciphertext is None:
        return None
    return TokenSet.from_json(decrypt(connection.oauth_ciphertext))


def write_tokens(connection: ProviderConnection, tokens: TokenSet | None) -> None:
    """Store a sign-in, or None to sign out; either way a new version."""
    connection.oauth_ciphertext = None if tokens is None else encrypt(tokens.to_json())
    connection.token_version = (connection.token_version or 0) + 1


@dataclass(frozen=True)
class _Held:
    token: TokenSet
    version: int


class ConnectionAccess:
    """A ChatGPT connection's access token, refreshed by one process at a time.

    Every database transaction here is BEGIN IMMEDIATE (`shared.db`), so a
    refresh holds the write lock across its one HTTP call: a second process
    waits, then sees the version move and uses the token the first stored.
    """

    def __init__(self, engine: Engine, connection_id: int) -> None:
        self._engine = engine
        self._connection_id = connection_id
        self._held: _Held | None = None

    async def __call__(self, refresh: bool) -> str:
        held = self._held
        if not refresh and held is not None and not held.token.due():
            return held.token.access_token
        seen = None if held is None else held.version
        self._held = await asyncio.to_thread(self._current, seen if refresh else None)
        return self._held.token.access_token

    def _current(self, refused_version: int | None) -> _Held:
        """The usable token, refreshing when it is due or the endpoint refused
        the one at `refused_version`."""
        with self._engine.begin() as db:
            held = self._stored(db)
            if held.version != refused_version and not held.token.due():
                return held
            try:
                reply = token_endpoint.refresh(
                    held.token.client_id, held.token.refresh_token
                )
            except token_endpoint.TokenRefusedError:
                self._write(db, None, held.version)
            else:
                fresh = held.token.refreshed(reply)
                self._write(db, fresh, held.version)
                return _Held(fresh, held.version + 1)
        # Raised once the sign-out has committed, so it outlives this request.
        raise SignInRequiredError

    def _stored(self, db: Connection) -> _Held:
        row = db.execute(
            select(_TABLE.c.oauth_ciphertext, _TABLE.c.token_version).where(
                _TABLE.c.id == self._connection_id
            )
        ).one_or_none()
        if row is None or row.oauth_ciphertext is None:
            raise SignInRequiredError
        return _Held(
            TokenSet.from_json(decrypt(row.oauth_ciphertext)), row.token_version
        )

    def _write(self, db: Connection, tokens: TokenSet | None, version: int) -> None:
        db.execute(
            update(_TABLE)
            .where(_TABLE.c.id == self._connection_id)
            .values(
                oauth_ciphertext=None if tokens is None else encrypt(tokens.to_json()),
                token_version=version + 1,
                # A refresh is not an edit; `updated_at` keeps meaning the user's.
                updated_at=_TABLE.c.updated_at,
            )
        )
