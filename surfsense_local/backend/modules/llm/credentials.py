"""BYO provider API keys, kept in the local database (see ProviderCredential)."""

from sqlalchemy.orm import Session

from modules.llm.models import ProviderCredential


def read_provider_key(session: Session, provider: str) -> str | None:
    row = session.get(ProviderCredential, provider)
    return row.api_key if row else None


def write_provider_key(session: Session, provider: str, api_key: str) -> None:
    row = session.get(ProviderCredential, provider)
    if row is None:
        session.add(ProviderCredential(provider=provider, api_key=api_key))
    else:
        row.api_key = api_key
    session.flush()


def clear_provider_key(session: Session, provider: str) -> bool:
    """Remove the key if present; returns whether there was one."""
    row = session.get(ProviderCredential, provider)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True
